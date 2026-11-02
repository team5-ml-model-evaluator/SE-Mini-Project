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
import io
import logging
import os
import random
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

import pandas as pd
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from baseline_model import run_baseline
from evaluation_metrics import (
    calculate_classification_metrics,
    calculate_regression_metrics,
)

from ..models import Run
from .catalogue import BY_KEY

STALE_AFTER_S = 15 * 60

# A run is considered lost when its supervising worker stops
# refreshing this lease.
STALE_AFTER_S = int(
    getattr(settings, "RUN_WORKER_LEASE_SECONDS", 10)
)

WORKER_EXIT_ERROR = (
    "The training worker stopped unexpectedly. Please start the run again."
)


def _touch_run_heartbeat(job_key):
    """Refresh the lease while the supervisor waits for training."""
    Run.objects.filter(
        job_key=job_key,
        state__in=[Run.QUEUED, Run.RUNNING],
    ).update(
        heartbeat_at=timezone.now()
    )


def _mark_worker_failed(job_key, message):
    """Fail active runs without overwriting terminal states."""
    Run.objects.filter(
        job_key=job_key,
        state__in=[Run.QUEUED, Run.RUNNING],
    ).update(
        state=Run.FAILED,
        error=message,
        finished_at=timezone.now(),
    )


def _terminate_process(process):
    """Terminate the child process and reap it."""
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)

    except ProcessLookupError:
        pass

    except OSError:
        logger.exception(
            "Could not send terminate signal to training process %s",
            process.pid,
        )
        try:
            process.terminate()
        except OSError:
            pass

    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)

    except ProcessLookupError:
        pass

    except OSError:
        logger.exception(
            "Could not kill training process %s",
            process.pid,
        )
        try:
            process.kill()
        except OSError:
            pass

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.error(
            "Training process %s did not exit after kill",
            process.pid,
        )


def _worker_command(job_key, queue_s, run_s):
    """Build the internal Django command for one isolated model run."""
    manage_py = Path(settings.BASE_DIR) / "manage.py"

    return [
        sys.executable,
        str(manage_py),
        "run_model_job",
        "--job-key",
        job_key,
        "--queue-seconds",
        str(queue_s),
        "--run-seconds",
        str(run_s),
    ]

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
    if run.batch_id:
        from ..batches import reconcile_batch
        reconcile_batch(run.batch)
    run.refresh_from_db()
    if not run.batch_id and run.state in (Run.QUEUED, Run.RUNNING):
    cutoff = timezone.now() - timedelta(seconds=STALE_AFTER_S)

    expired = Run.objects.filter(
        pk=run.pk,
        state__in=[Run.QUEUED, Run.RUNNING],
        heartbeat_at__lt=cutoff,
    ).update(
        state=Run.FAILED,
        error=(
            "The run was interrupted because its training worker "
            "stopped responding. Please start it again."
        ),
        finished_at=timezone.now(),
    )

    if expired:
        run.refresh_from_db()
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
    """Supervise one isolated training process and enforce its time limit.

    Synchronous mode is retained for deterministic tests.
    Normal requests and batch execution use a child process.
    """

    if getattr(settings, "STANDIN_RUN_SYNC", False):
        return _execute_in_worker(job_key, queue_s, run_s)

    close_old_connections()

    process = None

    timeout_s = float(
        getattr(settings, "TRAINING_JOB_TIMEOUT_SECONDS", 600)
    )

    heartbeat_interval = float(
        getattr(
            settings,
            "TRAINING_JOB_HEARTBEAT_INTERVAL_SECONDS",
            2,
        )
    )

    if timeout_s <= 0 or heartbeat_interval <= 0:
        _mark_worker_failed(
            job_key,
            "Training worker settings are invalid. "
            "Please contact an administrator.",
        )
        return

    try:
        _touch_run_heartbeat(job_key)

        popen_options = {
            "cwd": str(settings.BASE_DIR),
        }

        if os.name == "nt":
            popen_options["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            popen_options["start_new_session"] = True

        deadline = time.monotonic() + timeout_s

        process = subprocess.Popen(
            _worker_command(job_key, queue_s, run_s),
            **popen_options,
        )

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                _terminate_process(process)

                _mark_worker_failed(
                    job_key,
                    (
                        f"Training exceeded the {timeout_s:g}-second "
                        "time limit and was stopped. "
                        "Try a smaller dataset or a simpler model."
                    ),
                )
                return

            try:
                return_code = process.wait(
                    timeout=min(heartbeat_interval, remaining)
                )
                break

            except subprocess.TimeoutExpired:
                _touch_run_heartbeat(job_key)

        if return_code != 0:
            logger.error(
                "Training worker for run %s exited with status %s",
                job_key,
                return_code,
            )

            _mark_worker_failed(
                job_key,
                WORKER_EXIT_ERROR,
            )
            return

        # A successful process exit must also have saved a terminal state.
        run = (
            Run.objects
            .filter(job_key=job_key)
            .only("state")
            .first()
        )

        if run and run.state in (Run.QUEUED, Run.RUNNING):
            _mark_worker_failed(
                job_key,
                WORKER_EXIT_ERROR,
            )

    except OSError:
        logger.exception(
            "Could not start the training worker for run %s",
            job_key,
        )

        _mark_worker_failed(
            job_key,
            "The training worker could not be started. Please try again.",
        )

    except Exception:
        logger.exception(
            "Training supervisor failed for run %s",
            job_key,
        )

        if process is not None and process.poll() is None:
            _terminate_process(process)

        _mark_worker_failed(
            job_key,
            WORKER_EXIT_ERROR,
        )

    finally:
        close_old_connections()


def _execute_in_worker(job_key, queue_s, run_s):
    """Claim and execute one run inside its child process."""

    close_old_connections()

    try:
        time.sleep(queue_s)

        run = Run.objects.get(job_key=job_key)

        claimed = Run.objects.filter(
            pk=run.pk,
            state=Run.QUEUED,
        ).update(
            state=Run.RUNNING,
            started_at=timezone.now(),
            heartbeat_at=timezone.now(),
        )

        if not claimed:
            return

        run.refresh_from_db()

        time.sleep(run_s)

        try:
            run.result = _train_and_score(run)
            run.state = Run.COMPLETED
            run.error = ""

        except RunFailed as exc:
            run.state = Run.FAILED
            run.error = str(exc)

        except Exception as exc:
            logger.exception(
                "Run %s failed unexpectedly: %s",
                job_key,
                exc,
            )

            run.state = Run.FAILED
            run.error = (
                "The run stopped unexpectedly. "
                "Check the dataset and start it again."
            )

        run.finished_at = timezone.now()

        # Do not resurrect a run that was timed out or failed elsewhere.
        Run.objects.filter(
            pk=run.pk,
            state=Run.RUNNING,
        ).update(
            result=run.result,
            state=run.state,
            error=run.error,
            finished_at=run.finished_at,
            heartbeat_at=timezone.now(),
        )

    finally:
        close_old_connections()


def _train_and_score(run):
    if getattr(settings, "STANDIN_FORCE_BASELINE", False):
        return _train_and_score_standin(run)

    config = run.run_config
    target = config["target_column"]
    algorithm_key = config["algorithm"]
    algorithm = BY_KEY.get(algorithm_key)
    if not algorithm:
        raise RunFailed(f"Unsupported algorithm '{algorithm_key}'.")

    try:
        with run.dataset.file.open("rb") as handle:
            content = handle.read()
    except FileNotFoundError:
        raise RunFailed("The uploaded file for this dataset is missing on the server. Upload the CSV again.")
    except Exception as exc:
        logger.exception("Could not read dataset file for run %s: %s", run.job_key, exc)
        raise RunFailed("Could not read the dataset file. Upload the CSV again.")

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise RunFailed(f"Could not parse CSV dataset: {exc}")

    if target not in df.columns:
        raise RunFailed(f"Column '{target}' was not found in the dataset.")

    # Filter out missing/empty targets
    df = df[df[target].notna()].copy()
    if df[target].dtype == object:
        df = df[df[target].astype(str).str.strip() != ""].copy()

    if len(df) < 10:
        raise RunFailed(f"Column '{target}' has too few filled-in values to split into training and test sets.")

    feature_cols = [c for c in config.get("feature_columns", []) if c in df.columns and c != target]
    if not feature_cols:
        excluded = set(config.get("excluded_columns", [])) | {target}
        feature_cols = [c for c in df.columns if c not in excluded]

    if not feature_cols:
        raise RunFailed("No feature columns available to train the model. Choose at least one feature.")

    if algorithm.task == "classification":
        unique_targets = df[target].unique()
        if len(unique_targets) < 2:
            raise RunFailed(f"Column '{target}' has only one value, so there is nothing to tell apart. Choose a different target.")
    else:
        try:
            df[target] = pd.to_numeric(df[target], errors="raise")
        except (ValueError, TypeError):
            raise RunFailed(f"Column '{target}' is not numeric, but the chosen algorithm predicts numbers. Choose a numeric target or a classification algorithm.")

    random_seed = int(config.get("random_seed", 42))
    split_ratio = float(config.get("split_ratio", 0.8))
    order = list(range(len(df)))
    random.Random(random_seed).shuffle(order)
    cut = max(1, int(len(order) * split_ratio))
    train_idx = order[:cut]
    test_idx = order[cut:] or order[-1:]

    train_df = df.iloc[train_idx]
    test_df = df.iloc[test_idx]

    if algorithm.task == "classification":
        all_classes = sorted(list(set(train_df[target].dropna()) | set(test_df[target].dropna())))
        if len(all_classes) < 2:
            raise RunFailed(f"Column '{target}' has only one value, so there is nothing to tell apart. Choose a different target.")

    # One-hot encode categoricals in features, impute NaNs
    X_all = pd.get_dummies(df[feature_cols], drop_first=True, dummy_na=False, dtype=float)
    if X_all.shape[1] == 0:
        raise RunFailed("No valid feature columns available after encoding.")

    # Impute with training-set medians only, so test rows never leak into the fill values.
    med = X_all.iloc[train_idx].median().fillna(0.0)
    X_all = X_all.fillna(med)

    X_train = X_all.iloc[train_idx]
    X_test = X_all.iloc[test_idx]
    y_train = train_df[target]
    y_test = test_df[target]

    if algorithm.task == "classification":
        if y_train.nunique() < 2:
            raise RunFailed(
                f"The training rows contain only one value of '{target}', so the model cannot learn. "
                "Use a different target or a dataset with more rows of each class."
            )
        res = run_baseline(
            task="classification",
            model_name=algorithm_key,
            X_train=X_train,
            y_train=y_train,
            X_test=X_test,
            random_state=random_seed,
        )
        predictions = res["predictions"]
        metrics = calculate_classification_metrics(
            y_true=y_test.tolist(),
            y_pred=list(predictions),
            labels=all_classes,
        )
        return {
            "task": "classification",
            "execution": _execution_details(res["model"]),
            "standin": False,
            "test_rows": len(y_test),
            "accuracy": float(metrics["accuracy"]),
            "precision": float(metrics["precision"]),
            "recall": float(metrics["recall"]),
            "f1_score": float(metrics["f1_score"]),
            "confusion_matrix": metrics["confusion_matrix"],
            "labels": [str(c) for c in all_classes],
        }
    else:
        y_train_num = y_train.astype(float)
        y_test_num = y_test.astype(float)
        res = run_baseline(
            task="regression",
            model_name=algorithm_key,
            X_train=X_train,
            y_train=y_train_num,
            X_test=X_test,
            random_state=random_seed,
        )
        predictions = [float(p) for p in res["predictions"]]
        metrics = calculate_regression_metrics(
            y_true=y_test_num.tolist(),
            y_pred=predictions,
        )
        return {
            "task": "regression",
            "execution": _execution_details(res["model"]),
            "standin": False,
            "test_rows": len(y_test),
            "mae": float(metrics["mae"]),
            "mse": float(metrics["mse"]),
            "rmse": float(metrics["rmse"]),
            "r2": float(metrics["r2"]),
        }


def _execution_details(model):
    """Snapshot the effective settings for reports without changing the run interface."""
    return {
        "preprocessing": {
            "imputation": "Numeric missing values: training-set median, or 0 for an entirely missing training column",
            "encoding": "One-hot encoding (drop_first=True, dummy_na=False)",
            "scaling": "None",
        },
        "hyperparameters": model.get_params(deep=False),
    }


def _train_and_score_standin(run):
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
