# System Validation Report

## 1. Report Information

| Item | Details |
|---|---|
| Project | Web Based ML Model Evaluator |
| Team | Team 5 |
| Report | System Validation Report |
| Testing period specified in Part 3 | 2–6 November 2026 |
| Actual execution evidence available | 8 November 2026 |
| Test environment | Windows, Python 3.12, Django 5.2.18 |
| Test status | Partially completed |

## 2. Objective

The objective of system validation is to verify that the Web Based ML Model Evaluator satisfies its specified functional and non-functional requirements and behaves correctly under the tested conditions.

Testing is based on the project's Software Test Plan (STP), updated test cases, and the requirements documented in the Software Requirements Specification (SRS).

## 3. Test Environment

The following environment was used for the recorded test executions:

- Operating system: Windows
- Python version: 3.12
- Django version: 5.2.18
- Test framework: pytest
- Performance testing tool: Locust
- Application: Web Based ML Model Evaluator

## 4. System Validation Results

### 4.1 Performance Testing

| Test Case | Description | Recorded Result | Status |
|---|---|---|---|
| TC-PERF-001 | Verify non-training page response time under concurrent load | 1,487 requests; 0 failures; aggregate p95 17 ms. GET `/`: 17 ms; GET `/datasets/new/`: 15 ms; GET `/login`: 18 ms; POST `/login`: 1,100 ms. | Incomplete verification |
| TC-PERF-002 | Verify training execution time on the benchmark dataset | Five runs: 19.74 s, 31.43 s, 29.05 s, 28.07 s, and 26.11 s. Median: 28.07 s. | Pass |

**TC-PERF-001 acceptance condition:** The SRS requires p95 response time of no more than 2 seconds for non-training pages with 10 concurrent users over 5 minutes. The recorded request statistics meet the response-time threshold, but the full 5-minute duration and peak concurrency evidence have not yet been confirmed. Therefore, this test is not marked as fully passed.

**TC-PERF-002 acceptance condition:** The SRS requires the median of five training runs on the specified 50,000-row, 30-feature dataset to be no more than 120 seconds. The measured median was 28.07 seconds, so the recorded result passes the time threshold.

### 4.2 Functional and Integration Validation

The STP identifies the following test groups:

| Test Group | Validation Area | Status |
|---|---|---|
| TC-ACC | Account and authentication | Execution evidence pending |
| TC-DS | Dataset management | Execution evidence pending |
| TC-PP | Data preprocessing | Execution evidence pending |
| TC-MS | Model selection and configuration | Execution evidence pending |
| TC-TR | Training execution | Execution evidence pending |
| TC-EV | Model evaluation | Execution evidence pending |
| TC-RP | Results and reports | Execution evidence pending |
| TC-AD | Administration | Execution evidence pending |

These groups must be marked as passed only after their corresponding test cases have been executed and their results recorded.

### 4.3 Security Validation

The STP security validation areas include:

- TLS 1.2 or higher and HTTP-to-HTTPS redirection.
- Secure password storage using salted password hashing.
- Server-side role and resource-ownership enforcement.
- Safe upload handling and rejection of pickle/joblib files.
- Training-job timeout and failure isolation.
- Append-only audit logging.

Final execution evidence for these security checks has not been included in the results recorded in this report. They remain pending verification and must not be treated as passed based only on implementation or configuration.

### 4.4 Usability Validation

The SRS requires three out of three first-time users to complete the upload, training, and results-review workflow within five minutes.

Final usability validation results for the current build have not yet been confirmed. Earlier usability observations are not treated as final acceptance evidence.

## 5. Overall Result

The system has demonstrated a passing recorded result for the five-run training performance benchmark. The available Locust statistics also show low response times and no recorded request failures, but the complete concurrency and duration criteria still require confirmation.

Functional, security, and final usability validation evidence must be completed and attached before the system can be declared fully validated against the STP and SRS.

## 6. Supporting Evidence

The following evidence should be retained under `docs/test-reports/`:

- Locust statistics and history CSV files for TC-PERF-001.
- Five-run benchmark output for TC-PERF-002.
- Unit test JUnit XML report.
- Updated test case document and requirements traceability matrix.
- Security and usability test execution records.

## 7. Conclusion

System validation is partially completed. TC-PERF-002 passed its recorded performance threshold, while TC-PERF-001 still requires confirmation of the full load-test duration and concurrency. The remaining functional, security, and usability test groups require documented execution results before final validation sign-off.