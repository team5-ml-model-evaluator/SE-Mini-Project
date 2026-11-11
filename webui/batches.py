"""Task-aware, idempotent batch creation and a bounded local training queue."""
import hashlib
import json
import logging
import uuid
import threading
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import numpy as np
import pandas as pd
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from .models import Run, RunBatch
from .standins import runs
from .standins.catalogue import ALGORITHMS, BY_KEY
from .target_validation import validate_classification_target

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="model-comparison")
TOKEN_SALT = "webui.run-batch"
LEASE_SECONDS = int(getattr(settings, "RUN_WORKER_LEASE_SECONDS", 7))
HEARTBEAT_INTERVAL_SECONDS = 2
_lease_lock = threading.Lock()
_live_batches = set()
_heartbeat_thread = None
MAX_LOCAL_BATCHES = 8
_queue_slots = threading.BoundedSemaphore(MAX_LOCAL_BATCHES)
_reserved_batches = set()


def _release_batch(batch_id):
    with _lease_lock:
        _live_batches.discard(batch_id)
        reserved = batch_id in _reserved_batches
        _reserved_batches.discard(batch_id)
    if reserved:
        _queue_slots.release()


def _fail_pending_batch(batch_id, message):
    Run.objects.filter(batch_id=batch_id, state=Run.QUEUED).update(
        state=Run.FAILED, error=message, finished_at=timezone.now())
    RunBatch.objects.filter(pk=batch_id).update(active=False)


def _refresh_leases():
    with _lease_lock:
        ids = list(_live_batches)
    if ids:
        RunBatch.objects.filter(pk__in=ids, active=True).update(heartbeat_at=timezone.now())


def _heartbeat_loop():
    while True:
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        close_old_connections()
        try:
            _refresh_leases()
        except Exception:
            logger.exception("Could not refresh the evaluation worker heartbeat")
        finally:
            close_old_connections()


def _register_batch(batch_id):
    global _heartbeat_thread
    with _lease_lock:
        _live_batches.add(batch_id)
        if _heartbeat_thread is None:
            _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True, name="evaluation-heartbeat")
            _heartbeat_thread.start()


def reconcile_batch(batch):
    """Expire lost workers, rather than expiring models merely because they waited."""
    batch.refresh_from_db(fields=["active", "heartbeat_at"])
    cutoff = timezone.now() - timedelta(seconds=LEASE_SECONDS)
    if batch.active and batch.heartbeat_at < cutoff:
        with transaction.atomic():
            expired = RunBatch.objects.filter(pk=batch.pk, active=True, heartbeat_at__lt=cutoff).update(active=False)
            if expired:
                Run.objects.filter(batch=batch, state__in=[Run.QUEUED, Run.RUNNING]).update(
                    state=Run.FAILED, error="The evaluation was interrupted. Please run the models again.",
                    finished_at=timezone.now())
                batch.active = False


def _fingerprint(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def batch_token(owner, dataset, config):
    return signing.dumps({"id": str(uuid.uuid4()), "owner": owner.pk, "dataset": str(dataset.pk),
                          "config": _fingerprint(config)}, salt=TOKEN_SALT)


def suitable_algorithms(config):
    algorithm = BY_KEY.get(config.get("algorithm"))
    if algorithm is None:
        raise ValidationError("Choose an algorithm before running the models.")
    return [item for item in ALGORITHMS if item.task == algorithm.task]


def _validate_target(dataset, config, algorithms):
    target = config.get("target_column")
    features = config.get("feature_columns")
    if (target not in dataset.column_names or not isinstance(features, list) or not features
            or any(name not in dataset.column_names or name == target for name in features)):
        raise ValidationError("Choose a target and at least one valid feature column before running the models.")
    validate_classification_target(dataset, target, algorithms[0].key)
    try:
        with dataset.file.open("rb") as handle:
            values = pd.read_csv(handle, usecols=[target])[target].dropna()
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValidationError("Could not read the target column. Upload the CSV again.") from exc
    if pd.api.types.is_object_dtype(values) or pd.api.types.is_string_dtype(values):
        values = values[values.astype(str).str.strip() != ""]
    if len(values) < 10:
        raise ValidationError("The target needs at least 10 filled-in rows for training and evaluation.")
    if algorithms[0].task == "classification":
        if values.nunique() < 2:
            raise ValidationError("The target has only one value. Choose a target with at least two categories.")
    else:
        numeric = pd.to_numeric(values, errors="coerce")
        if numeric.isna().any() or not np.isfinite(numeric).all():
            raise ValidationError("Regression models require a finite numeric target. Choose a numeric target or classification models.")


def start_batch(owner, dataset, config, token, selected_algorithms=None):
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=3600)
        batch_id = uuid.UUID(payload["id"])
        valid = (payload["owner"] == owner.pk and payload["dataset"] == str(dataset.pk)
                 and payload["config"] == _fingerprint(config))
    except (signing.BadSignature, TypeError, ValueError, KeyError) as exc:
        raise ValidationError("This run request expired or is invalid. Review the settings and try again.") from exc
    if not valid:
        raise ValidationError("The settings changed. Review them before running all models.")
    existing = RunBatch.objects.filter(pk=batch_id, owner=owner, dataset=dataset).first()
    if existing:
        return existing
    active = RunBatch.objects.filter(owner=owner, active=True).first()
    if active and get_batch_status(active)["active"]:
        return active
    algorithms = suitable_algorithms(config)
    selected_keys = selected_algorithms or config.get("selected_algorithms")
    if selected_keys and isinstance(selected_keys, list) and len(selected_keys) >= 2:
        filtered = [a for a in algorithms if a.key in selected_keys]
        if filtered:
            algorithms = filtered
    _validate_target(dataset, config, algorithms)
    try:
        with transaction.atomic():
            batch = RunBatch.objects.create(id=batch_id, owner=owner, dataset=dataset,
                                            task=algorithms[0].task, run_config=deepcopy(config))
            for algorithm in algorithms:
                run_config = deepcopy(config)
                run_config["algorithm"] = algorithm.key
                Run.objects.create(owner=owner, dataset=dataset, batch=batch,
                                   job_key="r-" + uuid.uuid4().hex[:12], run_config=run_config)
            transaction.on_commit(lambda: schedule_batch(batch.pk))
        return batch
    except IntegrityError:
        # The database constraint also protects simultaneous submissions.
        existing = RunBatch.objects.filter(pk=batch_id, owner=owner).first()
        active = RunBatch.objects.filter(owner=owner, active=True).first()
        if existing or active:
            return existing or active
        raise


def schedule_batch(batch_id):
    try:
        if getattr(settings, "STANDIN_RUN_SYNC", False):
            execute_batch(batch_id)
        else:
            if not _queue_slots.acquire(blocking=False):
                _fail_pending_batch(batch_id, "The model queue is busy. Please try again shortly.")
                return
            with _lease_lock:
                _reserved_batches.add(batch_id)
            _register_batch(batch_id)
            _executor.submit(execute_batch, batch_id)
    except RuntimeError:
        logger.exception("Could not schedule batch %s", batch_id)
        _fail_pending_batch(batch_id, "The evaluation could not start. Please try again.")
        _release_batch(batch_id)


def execute_batch(batch_id):
    """Run one model at a time; one model failure does not cancel the others."""
    close_old_connections()
    try:
        RunBatch.objects.filter(pk=batch_id, active=True).update(heartbeat_at=timezone.now())
        keys = list(Run.objects.filter(batch_id=batch_id).order_by("pk").values_list("job_key", flat=True))
        for key in keys:
            if not Run.objects.filter(job_key=key, state=Run.QUEUED).exists():
                continue
            try:
                # Batch execution uses no artificial UI demo delay.
                runs._execute(key, queue_s=0, run_s=0)
            except Exception:
                logger.exception("Batch model %s failed", key)
                Run.objects.filter(job_key=key).update(state=Run.FAILED,
                    error="This model could not finish. Other models will continue.", finished_at=timezone.now())
    except Exception:
        logger.exception("Batch %s was interrupted", batch_id)
        Run.objects.filter(batch_id=batch_id, state__in=[Run.QUEUED, Run.RUNNING]).update(
            state=Run.FAILED, error="The evaluation was interrupted. Please try again.", finished_at=timezone.now())
    finally:
        try:
            RunBatch.objects.filter(pk=batch_id).update(active=False)
        finally:
            _release_batch(batch_id)
            close_old_connections()


def get_batch_status(batch):
    reconcile_batch(batch)
    jobs = []
    for run in batch.runs.defer("result").order_by("pk"):
        algorithm = BY_KEY.get(run.run_config.get("algorithm"))
        jobs.append({"key": run.job_key, "algorithm": algorithm.label if algorithm else "Unknown model",
                     "state": run.state, "elapsed_s": run.elapsed_s, "error": run.error or None})
    completed = sum(job["state"] == Run.COMPLETED for job in jobs)
    failed = sum(job["state"] == Run.FAILED for job in jobs)
    active = any(job["state"] in (Run.QUEUED, Run.RUNNING) for job in jobs)
    if not active and batch.active:
        RunBatch.objects.filter(pk=batch.pk).update(active=False)
        batch.active = False
    return {"jobs": jobs, "total": len(jobs), "completed": completed, "failed": failed,
            "finished": completed + failed, "active": active,
            "version": "|".join(f"{job['key']}:{job['state']}" for job in jobs)}
