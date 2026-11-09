# Sprint 3 test cases

Source of requirements and suite IDs: SRS v1.1 and the Web Based ML Model
Evaluator STP. Automated execution recorded here used
`.\.venv\Scripts\python.exe -m pytest -q` on the current
`part3-testing-and-reports` branch. Result: **235 passed, 59 subtests passed**.
Pass means the referenced automated checks completed successfully. Manual or
deployment-only checks remain Not Run unless their specified evidence exists.

## TC-ACC - Account and access management

### TC-ACC-01
- **SRS requirement ID:** MLE-F-001
- **Objective:** Register with an email address not already assigned to an account.
- **Preconditions and test data:** Registration page is available; use a valid username, an eight-character-or-longer password, and an unused email. Also try an existing email with different casing.
- **Steps:** 1. Submit the unique email and matching passwords. 2. Submit the same email with different casing and a new username.
- **Expected result:** The first account is created with the default User role; the duplicate email is rejected with an explanatory error and no second account is created.
- **Actual result:** Automated registration and duplicate-email checks passed.
- **Status:** Pass
- **Evidence reference:** `tests/test_authentication.py`; full regression command above.

### TC-ACC-02
- **SRS requirement ID:** MLE-F-002
- **Objective:** Authenticate by email and password before allowing access to protected data.
- **Preconditions and test data:** Existing account with a registered email and password; one signed-out client.
- **Steps:** 1. Sign in using the email and password. 2. Request a protected page without signing in. 3. Verify an existing username-only account can still use its username.
- **Expected result:** Valid email credentials authenticate; protected pages require authentication; legacy accounts are not made inaccessible.
- **Actual result:** Email login, legacy username login, and login-required checks passed.
- **Status:** Pass
- **Evidence reference:** `tests/test_authentication.py`, `webui/test_administration.py`; full regression command above.

### TC-ACC-03
- **SRS requirement ID:** MLE-F-003
- **Objective:** Restrict administrator pages and actions to administrators.
- **Preconditions and test data:** A normal registered user and an administrator account.
- **Steps:** 1. Request each administrator page as the normal user. 2. Attempt account-status changes. 3. Request an administrator page as an administrator.
- **Expected result:** Normal-user requests are forbidden; authorized administrator requests succeed.
- **Actual result:** Administrator page and action authorization tests passed.
- **Status:** Pass
- **Evidence reference:** `tests/test_authentication.py`, `webui/test_administration.py`; full regression command above.

## TC-DS - Dataset upload, validation, profiling, and ownership

### TC-DS-01
- **SRS requirement ID:** MLE-F-010
- **Objective:** Accept a valid tabular CSV within the configured upload-size limit.
- **Preconditions and test data:** Signed-in user; well-formed UTF-8 CSV with a header, at least 20 rows, and at least two columns.
- **Steps:** 1. Upload a valid CSV. 2. Upload a file exactly at the configured test limit.
- **Expected result:** Both valid files are accepted and the dataset metadata and file are stored.
- **Actual result:** Valid upload and exact-limit checks passed.
- **Status:** Pass
- **Evidence reference:** `webui/tests.py`, `datasets/tests.py`; full regression command above.

### TC-DS-02
- **SRS requirement ID:** MLE-F-011
- **Objective:** Reject uploads with an invalid extension, malformed structure, insufficient rows, or excessive size.
- **Preconditions and test data:** Signed-in user; invalid extension, malformed CSV, 19-row CSV, and file larger than a lowered test limit.
- **Steps:** 1. Submit each invalid file. 2. Check the response, database, and storage after each rejection.
- **Expected result:** Each invalid upload is rejected with guidance and is not stored.
- **Actual result:** Invalid-extension, malformed-row, undersized, and oversized checks passed.
- **Status:** Pass
- **Evidence reference:** `webui/tests.py`, `datasets/tests.py`; full regression command above.

### TC-DS-03
- **SRS requirement ID:** MLE-F-012
- **Objective:** Profile row and column counts, inferred types, and missing values.
- **Preconditions and test data:** Valid CSV containing integer, decimal, and text values plus missing tokens.
- **Steps:** 1. Upload or profile the CSV. 2. Compare the returned profile with the known header, row count, inferred types, and missing-value counts.
- **Expected result:** The profile reports the correct dimensions, types, and missing-value statistics.
- **Actual result:** Profiling and upload-profile checks passed.
- **Status:** Pass
- **Evidence reference:** `datasets/tests.py`, `webui/tests.py`; full regression command above.

### TC-DS-04
- **SRS requirement ID:** MLE-F-013
- **Objective:** Enforce dataset ownership on server-side requests.
- **Preconditions and test data:** Two authenticated users and a dataset owned by the first user.
- **Steps:** 1. Request the dataset as its owner. 2. Change the dataset identifier and request it as the other user. 3. Request an unknown identifier.
- **Expected result:** Owner access succeeds; cross-user access returns HTTP 403; unknown identifiers return HTTP 404.
- **Actual result:** Ownership and identifier-tampering checks passed.
- **Status:** Pass
- **Evidence reference:** `datasets/tests.py`, `datasets/test_isolation_edge_cases.py`; full regression command above.

## TC-PP - Preprocessing pipeline

### TC-PP-01
- **SRS requirement ID:** MLE-F-020
- **Objective:** Select a target and mark remaining columns as features or excluded.
- **Preconditions and test data:** Dataset with multiple columns and an authenticated owner.
- **Steps:** 1. Select a target. 2. Assign feature and excluded roles. 3. Submit with no remaining features.
- **Expected result:** Valid selections are saved; an invalid selection with no features is rejected.
- **Actual result:** Target/feature form checks passed.
- **Status:** Pass
- **Evidence reference:** `webui/tests.py`, `preprocessing/tests.py`; full regression command above.

### TC-PP-02
- **SRS requirement ID:** MLE-F-021
- **Objective:** Apply the selected missing-value strategy.
- **Preconditions and test data:** Dataset with missing numeric and categorical values; mean, median, mode, and row-deletion options.
- **Steps:** 1. Run preprocessing once for each strategy. 2. Check the transformed data and selected configuration.
- **Expected result:** Each strategy handles missing values as specified and records the selected setting.
- **Actual result:** Preprocessing tests passed.
- **Status:** Pass
- **Evidence reference:** `preprocessing/tests.py`, `pipeline/tests.py`; full regression command above.

### TC-PP-03
- **SRS requirement ID:** MLE-F-022
- **Objective:** Apply configured encoding and scaling.
- **Preconditions and test data:** Dataset with categorical and numeric features; one-hot/label encoding and standard/min-max scaling options.
- **Steps:** 1. Run the supported encoding/scaling combinations. 2. Check the transformed feature data and recorded options.
- **Expected result:** The selected transformations are applied and captured in run configuration/results.
- **Actual result:** Preprocessing and configuration tests passed.
- **Status:** Pass
- **Evidence reference:** `preprocessing/tests.py`, `pipeline/tests.py`, `tests/test_model_evaluation_integration.py`; full regression command above.

### TC-PP-04
- **SRS requirement ID:** MLE-F-023
- **Objective:** Create a reproducible seeded train/test split within the supported ratio range.
- **Preconditions and test data:** Valid dataset, fixed random seed, and split ratios from 50:50 through 90:10.
- **Steps:** 1. Run the split with a supported ratio and seed. 2. Repeat with the same inputs. 3. Try values outside the supported range.
- **Expected result:** Repeated inputs produce the same split; invalid ratios are rejected.
- **Actual result:** Seeded split and validation tests passed.
- **Status:** Pass
- **Evidence reference:** `pipeline/tests.py`, `tests/test_model_evaluation_integration.py`; full regression command above.

## TC-MS - Model selection and hyperparameters

### TC-MS-01
- **SRS requirement ID:** MLE-F-030
- **Objective:** Verify the five supported classification algorithms are selectable and trainable.
- **Preconditions and test data:** Valid classification dataset and supported model configuration.
- **Steps:** 1. Inspect available classifiers. 2. Train a run with each supported classifier.
- **Expected result:** All five classifiers are available and produce a valid run result.
- **Actual result:** Model catalogue and training tests passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_batches.py`, `tests/test_model_evaluation_integration.py`, `webui/standins/catalogue.py`; full regression command above.

### TC-MS-02
- **SRS requirement ID:** MLE-F-031
- **Objective:** Verify the three supported regression algorithms are selectable and trainable.
- **Preconditions and test data:** Valid numeric-target dataset and supported model configuration.
- **Steps:** 1. Inspect available regressors. 2. Train a run with each supported regressor.
- **Expected result:** All three regressors are available and produce valid regression results.
- **Actual result:** Regression catalogue and run tests passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_batches.py`, `webui/test_runs.py`, `tests/test_model_evaluation_integration.py`; full regression command above.

### TC-MS-03
- **SRS requirement ID:** MLE-F-032
- **Objective:** Validate hyperparameter values and defaults.
- **Preconditions and test data:** Model forms and supported/unsupported hyperparameter values.
- **Steps:** 1. Submit defaults and values within range. 2. Submit invalid values and types.
- **Expected result:** Valid values/defaults are accepted; invalid values are rejected with an actionable error.
- **Actual result:** Hyperparameter validation tests passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_forms.py`, `tests/test_training_jobs.py`; full regression command above.

## TC-TR - Background training execution

### TC-TR-01
- **SRS requirement ID:** MLE-F-040
- **Objective:** Keep the interface responsive while a run executes in a separate worker.
- **Preconditions and test data:** Authenticated owner and queued run.
- **Steps:** 1. Start a child worker. 2. Request the run page while it is active.
- **Expected result:** The run request is asynchronous and the run page remains available.
- **Actual result:** The run page returned HTTP 200 while the child worker was active.
- **Status:** Pass
- **Evidence reference:** `webui/test_runs.py::AsyncWorkerFailureTests.test_async_worker_failure_is_reported_within_10_seconds`; full regression command above.

### TC-TR-02
- **SRS requirement ID:** MLE-F-041
- **Objective:** Verify Queued, Running, Completed, and Failed states and display a failure reason.
- **Preconditions and test data:** Runs transitioned through each supported state, including one child-process failure.
- **Steps:** 1. Observe the status endpoint and run page for each state. 2. Cause a worker process to exit unsuccessfully.
- **Expected result:** The stored/displayed state is correct and a useful failure reason is persisted.
- **Actual result:** State, failure-reason, and child-exit checks passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_runs.py`; full regression command above.

### TC-TR-03
- **SRS requirement ID:** MLE-F-042
- **Objective:** Reproduce a run from its stored configuration and seed.
- **Preconditions and test data:** A fixed dataset, model configuration, and random seed.
- **Steps:** 1. Execute the same stored run configuration twice. 2. Compare the recorded configuration and results.
- **Expected result:** The stored settings and seed permit reproducible execution.
- **Actual result:** Replaying the stored run configuration and seed produced the same result.
- **Status:** Pass
- **Evidence reference:** `webui/test_runs.py::ResultsTests.test_stored_configuration_and_seed_reproduce_the_run_result`; full regression command above.

## TC-EV - Metrics and run comparison

### TC-EV-01
- **SRS requirement ID:** MLE-F-050
- **Objective:** Verify classification metrics and confusion matrix output.
- **Preconditions and test data:** Classification fixture with known expected metrics.
- **Steps:** 1. Evaluate the fixture. 2. Compare accuracy, precision, recall, F1, and confusion matrix with expected values.
- **Expected result:** Metrics and matrix match their reference values.
- **Actual result:** Classification metric and golden-fixture tests passed.
- **Status:** Pass
- **Evidence reference:** `tests/test_evaluation_metrics.py`, `tests/test_golden_fixtures.py`, `webui/test_runs.py`; full regression command above.

### TC-EV-02
- **SRS requirement ID:** MLE-F-051
- **Objective:** Verify regression metrics.
- **Preconditions and test data:** Regression fixture with known expected values.
- **Steps:** 1. Evaluate the fixture. 2. Compare MAE, MSE, RMSE, and R-squared with expected values.
- **Expected result:** Regression metrics match their reference values.
- **Actual result:** Regression metric and golden-fixture tests passed.
- **Status:** Pass
- **Evidence reference:** `tests/test_evaluation_metrics.py`, `tests/test_golden_fixtures.py`, `webui/test_runs.py`; full regression command above.

### TC-EV-03
- **SRS requirement ID:** MLE-F-052
- **Objective:** Compare two or more completed runs.
- **Preconditions and test data:** At least two completed, owned runs for the same dataset.
- **Steps:** 1. Select two or more completed runs. 2. Request the comparison. 3. Try a foreign or incomplete run identifier.
- **Expected result:** Selected completed runs are compared; unauthorized or ineligible runs are rejected.
- **Actual result:** Comparison selection and ownership tests passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_comparison.py`, `webui/test_batches.py`; full regression command above.

## TC-RP - Report generation and CSV export

### TC-RP-01
- **SRS requirement ID:** MLE-F-060
- **Objective:** Download a complete evaluation report.
- **Preconditions and test data:** Owned completed run with valid result and configuration.
- **Steps:** 1. Download HTML and PDF reports. 2. Check run details, effective settings, and metrics. 3. Try a foreign run identifier.
- **Expected result:** Reports contain the expected run details; unauthorized reports are forbidden.
- **Actual result:** HTML/PDF report and authorization tests passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_reports.py`; full regression command above.

### TC-RP-02
- **SRS requirement ID:** MLE-F-061
- **Objective:** Verify CSV export matches comparison values and ordering.
- **Preconditions and test data:** Two or more completed runs selected for comparison.
- **Steps:** 1. Export the comparison CSV. 2. Parse it with a CSV reader. 3. Compare headers, metric rows, and display order with the page.
- **Expected result:** CSV values and ordering match the on-screen comparison.
- **Actual result:** CSV fidelity and report export tests passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_reports.py`, `webui/test_comparison.py`; full regression command above.

## TC-AD - Account and catalogue administration

### TC-AD-01
- **SRS requirement ID:** MLE-F-062
- **Objective:** List, deactivate, and reactivate accounts.
- **Preconditions and test data:** Administrator and ordinary user accounts.
- **Steps:** 1. List/search accounts. 2. Deactivate and reactivate a user. 3. Try the actions as an ordinary user.
- **Expected result:** Authorized status changes are stored and audited; normal users receive HTTP 403.
- **Actual result:** Account administration, authorization, and audit tests passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_administration.py`; full regression command above.

### TC-AD-02
- **SRS requirement ID:** MLE-F-063
- **Objective:** List and safely remove dataset catalogue entries.
- **Preconditions and test data:** Administrator, unused dataset, and dataset referenced by a run.
- **Steps:** 1. List catalogue metadata. 2. Delete the unused dataset. 3. Attempt to delete the referenced dataset. 4. Check file, database, and audit state.
- **Expected result:** Successful deletion removes the dataset/file and creates exactly one success audit event; in-use deletion is blocked and not recorded as successful.
- **Actual result:** Successful and blocked deletion, file consistency, and audit assertions passed.
- **Status:** Pass
- **Evidence reference:** `datasets/test_catalogue.py`; full regression command above.

## TC-PERF - Response time and training duration

### TC-PERF-01
- **SRS requirement ID:** MLE-NF-001
- **Objective:** Measure 95th-percentile response time with 10 concurrent users.
- **Preconditions and test data:** Provisioned test environment, 10-user load profile, and response-time collection.
- **Steps:** 1. Run the 10-user load profile. 2. Calculate the 95th percentile. 3. Compare with the two-second limit.
- **Expected result:** 95th-percentile response time is at most two seconds.
- **Actual result:** Not run; no 10-user load measurement was collected.
- **Status:** Not Run
- **Evidence reference:** STP section 3; `locustfile.py` is a load-test harness, but no execution result is available.

### TC-PERF-02
- **SRS requirement ID:** MLE-NF-002
- **Objective:** Measure training time on the 50,000 by 30 reference dataset.
- **Preconditions and test data:** Generated SRS reference dataset; five model-training repetitions.
- **Steps:** 1. Train the reference model five times. 2. Calculate the median execution time. 3. Compare with the 120-second limit.
- **Expected result:** Median training time is at most 120 seconds.
- **Actual result:** Five measured runs had a median of 24.60 seconds, below the 120-second limit.
- **Status:** Pass
- **Evidence reference:** `tests/test_performance_benchmark.py`, `tests/conftest.py`; full regression command above.

## TC-REL - Failure isolation

### TC-REL-01
- **SRS requirement ID:** MLE-NF-003
- **Objective:** Confirm a failed worker does not make the application unusable.
- **Preconditions and test data:** A queued run and a child process configured to exit unsuccessfully.
- **Steps:** 1. Start the child process. 2. Request the run page while it is active. 3. Wait for failure and inspect state/reason within 10 seconds.
- **Expected result:** The run is Failed with a useful reason within 10 seconds and the application continues serving requests.
- **Actual result:** Genuine child-process failure was persisted and the run page remained available.
- **Status:** Pass
- **Evidence reference:** `webui/test_runs.py::AsyncWorkerFailureTests.test_async_worker_failure_is_reported_within_10_seconds`; full regression command above.

## TC-UX - Usability and keyboard accessibility

### TC-UX-01
- **SRS requirement ID:** MLE-NF-004
- **Objective:** Verify first-time task completion and keyboard-only reachability.
- **Preconditions and test data:** Three first-time participants, a supported browser, and a keyboard-only test setup.
- **Steps:** 1. Ask each participant to complete the first-use workflow and record time. 2. Traverse all controls using only the keyboard.
- **Expected result:** Participants finish within five minutes and every control is keyboard reachable.
- **Actual result:** Not run; no participant walkthrough evidence was provided.
- **Status:** Not Run
- **Evidence reference:** STP section 5; automated accessibility checks are not a substitute for the timed participant walkthrough.

## TC-MNT - Core-module test coverage

### TC-MNT-01
- **SRS requirement ID:** MLE-NF-005
- **Objective:** Measure unit-test line coverage for the three core modules.
- **Preconditions and test data:** Coverage-enabled test environment and the complete core-module test suite.
- **Steps:** 1. Run the coverage suite. 2. Record line coverage separately for preprocessing, model selection, and evaluation.
- **Expected result:** Each core module has at least 60 percent unit-test line coverage.
- **Actual result:** Not run; the regression run did not collect a coverage report.
- **Status:** Not Run
- **Evidence reference:** STP section 3; no coverage artifact was generated for this execution.

## TC-OPS - Retention and UTC timestamps

### TC-OPS-01
- **SRS requirement ID:** MLE-NF-006
- **Objective:** Confirm project-start run/audit records remain retrievable and timestamps are UTC.
- **Preconditions and test data:** Run, batch, and audit records with project-start timestamps.
- **Steps:** 1. Retrieve the older run and audit record. 2. Attempt protected deletion of referenced records. 3. Inspect Run, RunBatch, and AuditLog timestamps.
- **Expected result:** Historical records remain retrievable; retention protections prevent deletion; timestamps are timezone-aware with zero UTC offset.
- **Actual result:** Historical retrieval, protected deletion, and UTC timestamp assertions passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_administration.py::AdministratorManagementTests.test_project_start_history_is_retrievable_and_timestamps_are_utc`; full regression command above.

## TC-SEC - Security validation

### TC-SEC-01
- **SRS requirement ID:** MLE-SR-001
- **Objective:** Verify deployed HTTPS and TLS 1.2 or higher.
- **Preconditions and test data:** Deployed host and TLS inspection tool.
- **Steps:** 1. Request the host over HTTP and HTTPS. 2. Inspect negotiated TLS versions and the redirect.
- **Expected result:** HTTP redirects to HTTPS and no TLS version below 1.2 is accepted.
- **Actual result:** Not run; no deployed-host TLS evidence was collected.
- **Status:** Not Run
- **Evidence reference:** STP section 5.1; deployment endpoint was not supplied.

### TC-SEC-02
- **SRS requirement ID:** MLE-SR-002
- **Objective:** Verify passwords are salted one-way hashes and never appear in application logs.
- **Preconditions and test data:** Two accounts with the same known password and captured application logs for failed and successful login.
- **Steps:** 1. Inspect stored password encodings. 2. Verify the password using Django's password-checking API. 3. Compare hashes and inspect captured logs.
- **Expected result:** Passwords are salted hashes, verify through Django, and raw credentials are absent from logs.
- **Actual result:** Hash format, salt uniqueness, password verification, and log assertions passed.
- **Status:** Pass
- **Evidence reference:** `tests/test_authentication.py`; full regression command above.

### TC-SEC-03
- **SRS requirement ID:** MLE-SR-003
- **Objective:** Enforce server-side ownership and role checks when identifiers are changed.
- **Preconditions and test data:** Two users, another user's dataset/run/report, and administrator endpoints.
- **Steps:** 1. Substitute identifiers for datasets, runs, and reports. 2. Request administrator pages/actions as a normal user.
- **Expected result:** Cross-user requests and administrator requests by normal users return HTTP 403.
- **Actual result:** Dataset, run, report, and admin authorization checks passed.
- **Status:** Pass
- **Evidence reference:** `datasets/tests.py`, `webui/test_runs.py`, `webui/test_reports.py`, `webui/test_administration.py`; full regression command above.

### TC-SEC-04
- **SRS requirement ID:** MLE-SR-004
- **Objective:** Reject a crafted pickle payload renamed with a `.csv` extension.
- **Preconditions and test data:** Signed-in user; crafted payload whose harmless marker would be set if unpickled.
- **Steps:** 1. Upload the payload as `payload.csv`. 2. Check the response, database, FileStore, loader calls, and marker.
- **Expected result:** Upload is rejected; no Dataset or stored file is left; neither `pickle.load` nor `joblib.load` is called; the marker remains unset.
- **Actual result:** All rejection, no-storage, no-loader, and no-execution assertions passed.
- **Status:** Pass
- **Evidence reference:** `datasets/tests.py::ValidateCsvTests.test_pickle_payload_with_csv_name_is_rejected_without_loading_or_storage`; full regression command above.

### TC-SEC-05
- **SRS requirement ID:** MLE-SR-005
- **Objective:** Terminate only the worker that exceeds its configured wall-clock limit.
- **Preconditions and test data:** Separate child processes for a timed-out run, a completed run, and a concurrent completed run.
- **Steps:** 1. Start all child processes. 2. Let one exceed a short test-configured timeout. 3. Preserve a completed result and observe the concurrent process.
- **Expected result:** Only the over-limit child is terminated and marked Failed; completed results are not overwritten and the concurrent process completes normally.
- **Actual result:** Timeout, child termination, terminal-result preservation, and concurrent-process checks passed.
- **Status:** Pass
- **Evidence reference:** `webui/test_runs.py::AsyncWorkerFailureTests.test_supervisor_timeout_stops_only_its_child_and_preserves_terminal_results`; full regression command above.

### TC-SEC-06
- **SRS requirement ID:** MLE-SR-006
- **Objective:** Verify exactly one audit event for login, upload, deletion, and administrative action, and enforce append-only records.
- **Preconditions and test data:** User/admin accounts; valid upload; unused and in-use datasets; existing audit events.
- **Steps:** 1. Perform each successful action and count its audit events. 2. Attempt a blocked deletion. 3. Try instance and bulk audit modification/deletion.
- **Expected result:** Each successful action has one actor/action/resource/outcome event with UTC timestamp; blocked deletion is not recorded as success; audit records cannot be modified or deleted.
- **Actual result:** Login, upload, deletion, administrative audit, blocked-deletion, and append-only checks passed.
- **Status:** Pass
- **Evidence reference:** `tests/test_authentication.py`, `webui/tests.py`, `datasets/test_catalogue.py`, `webui/test_administration.py`, `webui/test_audit.py`; full regression command above.
