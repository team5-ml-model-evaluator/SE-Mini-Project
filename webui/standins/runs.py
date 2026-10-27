"""STAND-IN for RunsApp and TrainingWorker (SAD interface 2).

The real RunsApp enqueues a run, and the real TrainingWorker trains the chosen algorithm and
computes metrics with scikit-learn (issues #12, #13). Until those are merged this module lets the
UI be built and tested end to end. It keeps the same shape as the SAD:

    start(owner, dataset, run_config) -> job_key      (RunsApp creates the record and enqueues)
    get_status(run)                  -> dict           (state, elapsed_s, error)

The stand-in worker does NOT train the chosen algorithm. It predicts the most frequent class
(classification) or the training mean (regression) on a held-out split, so the numbers are real
but only describe that trivial baseline. Results carry ``standin: True`` and the UI says so.

To swap: delete this file, point ``start`` and ``get_status`` in views.py at RunsApp, and keep
the result keys below (they match evaluation_metrics.py from issue #13).
"""
import csv
import random
import threading
import time
import uuid
from collections import Counter

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from ..models import Run
from .catalogue import BY_KEY

STALE_AFTER_S = 15 * 60


def start(owner, dataset, run_config):
    """Create the run record and hand it to the worker. Returns without waiting for the run."""
    run = Run.objects.create(job_key="r-" + uuid.uuid4().hex[:8], owner=owner, dataset=dataset, run_config=run_config)
    if getattr(settings, "STANDIN_RUN_SYNC", False):
        _execute(run.job_key, queue_s=0, run_s=0)
    else:
        threading.Thread(
            target=_execute, args=(run.job_key, settings.STANDIN_QUEUE_SECONDS, settings.STANDIN_RUN_SECONDS), daemon=True
        ).start()
    return run.job_key


def get_status(run):
    """The shape of GET /api/runs/<job_key>/status in the SAD."""
    run.refresh_from_db()
    if run.state in (Run.QUEUED, Run.RUNNING) and (timezone.now() - run.created_at).total_seconds() > STALE_AFTER_S:
        # The in-process worker died with the server; do not show "Running" forever.
        run.state, run.error, run.finished_at = Run.FAILED, "The run was interrupted before it finished. Start it again.", timezone.now()
        run.save(update_fields=["state", "error", "finished_at"])
    return {
        "job_key": run.job_key,
        "state": run.state,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "elapsed_s": run.elapsed_s,
        "error": run.error or None,
    }


# ---- worker -------------------------------------------------------------------------------------

class RunFailed(Exception):
    """A failure whose message tells the user what to change."""


def _execute(job_key, queue_s, run_s):
    close_old_connections()
    try:
        time.sleep(queue_s)
        run = Run.objects.get(job_key=job_key)
        run.state, run.started_at = Run.RUNNING, timezone.now()
        run.save(update_fields=["state", "started_at"])
        time.sleep(run_s)
        try:
            run.result = _train_and_score(run)
            run.state = Run.COMPLETED
        except RunFailed as exc:
            run.state, run.error = Run.FAILED, str(exc)
        except Exception:  # noqa: BLE001  the worker must never take the web process down (MLE-NF-003)
            run.state, run.error = Run.FAILED, "The run stopped unexpectedly. Check the dataset and start it again."
        run.finished_at = timezone.now()
        run.save()
    finally:
        close_old_connections()


def _train_and_score(run):
    config = run.run_config
    target = config["target_column"]
    with run.dataset.file.open("rb") as handle:
        text = handle.read().decode("utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    values = [row[target].strip() for row in rows if row.get(target, "").strip() != ""]
    if len(values) < 10:
        raise RunFailed(f"Column '{target}' has too few filled-in values to split into training and test sets.")
    order = list(range(len(values)))
    random.Random(config.get("random_seed", 42)).shuffle(order)
    cut = max(1, int(len(order) * config.get("split_ratio", 0.8)))
    train = [values[i] for i in order[:cut]]
    test = [values[i] for i in order[cut:]] or train[-1:]
    if BY_KEY[config["algorithm"]].task == "classification":
        return _classification(target, train, test)
    return _regression(target, train, test)


def _classification(target, train, test):
    if len(set(train + test)) < 2:
        raise RunFailed(f"Column '{target}' has only one value, so there is nothing to tell apart. Choose a different target.")
    majority = Counter(train).most_common(1)[0][0]
    pred = [majority] * len(test)
    labels = sorted(set(test) | {majority})
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for actual, guess in zip(test, pred):
        matrix[index[actual]][index[guess]] += 1
    total = len(test)
    precision = recall = f1 = 0.0
    for label in labels:
        i = index[label]
        tp = matrix[i][i]
        predicted = sum(matrix[r][i] for r in range(len(labels)))
        actual = sum(matrix[i])
        p = tp / predicted if predicted else 0.0
        r = tp / actual if actual else 0.0
        weight = actual / total
        precision += weight * p
        recall += weight * r
        f1 += weight * (2 * p * r / (p + r) if p + r else 0.0)
    accuracy = sum(matrix[i][i] for i in range(len(labels))) / total
    return {
        "task": "classification", "standin": True, "test_rows": total,
        "accuracy": accuracy, "precision": precision, "recall": recall, "f1_score": f1,
        "confusion_matrix": matrix, "labels": labels,
    }


def _regression(target, train, test):
    try:
        y_train = [float(v) for v in train]
        y_test = [float(v) for v in test]
    except ValueError:
        raise RunFailed(f"Column '{target}' is not numeric, but the chosen algorithm predicts numbers. Choose a numeric target or a classification algorithm.")
    mean = sum(y_train) / len(y_train)
    errors = [y - mean for y in y_test]
    mse = sum(e * e for e in errors) / len(errors)
    test_mean = sum(y_test) / len(y_test)
    ss_tot = sum((y - test_mean) ** 2 for y in y_test)
    return {
        "task": "regression", "standin": True, "test_rows": len(y_test),
        "mae": sum(abs(e) for e in errors) / len(errors), "mse": mse, "rmse": mse ** 0.5,
        "r2": 1 - (sum(e * e for e in errors) / ss_tot) if ss_tot else 0.0,
    }
