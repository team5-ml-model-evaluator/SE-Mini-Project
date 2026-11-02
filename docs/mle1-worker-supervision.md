# MLE-1: worker supervision and timeout handling

## Runtime design

The web request creates a `Run` in the `Queued` state and returns the run URL. The
existing `webui.standins.runs` module supervises a separate Django management-command
process (`run_model_job`) for each model. The child process claims the run, transitions it
to `Running`, performs preprocessing/model fitting/evaluation, and persists either a result
or a user-safe failure reason.

The supervisor waits for the child without blocking the web request. It refreshes the
`Run.heartbeat_at` lease while waiting. If the child exceeds the configured wall-clock limit,
the supervisor terminates the child process group and records the run as `Failed`. If a child
exits unexpectedly or cannot be started, the active run is marked `Failed`; terminal states
are never overwritten by a late supervisor update.

Batch execution continues to use the existing sequential model loop. Each model is run
through the same supervisor, so a timed-out or crashed model is failed independently and
the following models continue. Batch and individual-run heartbeats allow status requests
to reconcile workers that disappear without a clean exit.

## Configuration

- `TRAINING_JOB_TIMEOUT_SECONDS`: maximum wall-clock time per model run; defaults to `600`
  seconds (10 minutes).
- `TRAINING_JOB_HEARTBEAT_INTERVAL_SECONDS`: supervisor heartbeat interval; defaults to
  `2` seconds.
- `RUN_WORKER_LEASE_SECONDS`: stale-worker lease; defaults to `7` seconds. With the existing
  three-second browser polling interval, a lost worker is normally reported within about
  ten seconds after its last heartbeat.

`STANDIN_RUN_SYNC` remains a test/development-only escape hatch for deterministic synchronous
tests. The normal application path uses the supervised child process.

## Design deviation from the original SAD thread-based stand-in

The earlier in-process daemon-thread worker could catch Python exceptions but could not
reliably stop a scikit-learn fit that hangs. MLE-1 therefore replaces the normal execution
body with a supervised child process. This is an implementation-level refinement: the
`Run` status contract and user-facing Queued/Running/Completed/Failed states remain unchanged.
The child-process boundary enables a hard per-run timeout without terminating the Django
web process.

## Verification added

The worker-supervisor tests cover timeout termination, non-zero child exit handling, command
dispatch, persistence of child results, and heartbeat-based stale-run reconciliation. Existing
batch tests continue to cover model-at-a-time execution and continuation after an individual
model failure.
