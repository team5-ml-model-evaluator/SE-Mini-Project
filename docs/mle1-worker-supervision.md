# MLE-1: Worker Supervision and Timeout Handling

## Runtime Design

The web request creates a Run record in the Queued state and returns
the run URL.

The existing webui.standins.runs module supervises a separate Django
management-command process for each model.

The child process claims the run, transitions it to Running, performs
preprocessing, model fitting and evaluation, and persists either a
result or a user-safe failure reason.

The supervisor waits for the child process without blocking the web
request. It refreshes the Run.heartbeat_at lease while waiting.

If the child exceeds the configured wall-clock limit, the supervisor
terminates the child process group and records the run as Failed.

If a child exits unexpectedly or cannot be started, the active run is
marked as Failed. Terminal states are never overwritten by a late
supervisor update.

Batch execution continues to use the existing sequential model loop.
Each model is run through the same supervisor, so a timed-out or
crashed model is failed independently and subsequent models continue.

## Configuration

- TRAINING_JOB_TIMEOUT_SECONDS: maximum runtime per model run;
  default 600 seconds.
- TRAINING_JOB_HEARTBEAT_INTERVAL_SECONDS: supervisor heartbeat
  interval; default 2 seconds.
- RUN_WORKER_LEASE_SECONDS: stale-worker lease; default 7 seconds.

## Design Deviation from the Original SAD

The earlier in-process daemon-thread worker could catch Python
exceptions but could not reliably stop a scikit-learn fit that hangs.

MLE-1 replaces the normal execution body with a supervised child
process. This allows a hard per-run timeout without terminating the
Django web process.

The Run status contract and the user-facing
Queued, Running, Completed and Failed states remain unchanged.

## Verification

Tests cover timeout termination, non-zero child exit handling,
internal command dispatch, result preservation and heartbeat-based
stale-run reconciliation.

Existing batch tests continue to cover model-at-a-time execution and
continuation after an individual model failure.
