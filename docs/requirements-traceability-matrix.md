# Sprint 3 requirements traceability matrix

Source: Team 5 SRS v1.1 and the Web Based ML Model Evaluator STP. The current
`part3-testing-and-reports` branch and GitHub `main` were at the same commit
(`d2d6679`) when checked. SRS v1.1 MLE-F-001 and MLE-F-002 require unique-email
registration and email/password login; the prior username-based registration
and login did not meet those requirements. Registration now checks email
uniqueness and login accepts email while retaining legacy username login and
the existing user/administrator role model.

Execution command: `.\.venv\Scripts\python.exe -m pytest -q`

Execution result: **235 passed, 59 subtests passed**. Pass is limited to checks
actually executed. No 10-user response-time run, live TLS check, participant
usability walkthrough, or coverage report was collected; those cases remain
Not Run.

| Requirement ID | Requirement summary | STP test case | Execution status | Evidence / notes |
|---|---|---|---|---|
| MLE-F-001 | Unique email registration and password policy | TC-ACC-01 | Pass | [TC-ACC-01](./test-cases.md#tc-acc-01) |
| MLE-F-002 | Email/password authentication before protected access | TC-ACC-02 | Pass | [TC-ACC-02](./test-cases.md#tc-acc-02) |
| MLE-F-003 | Registered User / Administrator role separation | TC-ACC-03 | Pass | [TC-ACC-03](./test-cases.md#tc-acc-03) |
| MLE-F-010 | CSV upload up to configured size limit | TC-DS-01 | Pass | [TC-DS-01](./test-cases.md#tc-ds-01) |
| MLE-F-011 | Extension, structure, and minimum-size validation | TC-DS-02 | Pass | [TC-DS-02](./test-cases.md#tc-ds-02) |
| MLE-F-012 | Dataset profiling and missing-value statistics | TC-DS-03 | Pass | [TC-DS-03](./test-cases.md#tc-ds-03) |
| MLE-F-013 | Dataset ownership isolation | TC-DS-04 | Pass | [TC-DS-04](./test-cases.md#tc-ds-04) |
| MLE-F-020 | Target, feature, and exclusion selection | TC-PP-01 | Pass | [TC-PP-01](./test-cases.md#tc-pp-01) |
| MLE-F-021 | Missing-value handling strategies | TC-PP-02 | Pass | [TC-PP-02](./test-cases.md#tc-pp-02) |
| MLE-F-022 | Categorical encoding and numeric scaling | TC-PP-03 | Pass | [TC-PP-03](./test-cases.md#tc-pp-03) |
| MLE-F-023 | Seeded train/test split within supported ratios | TC-PP-04 | Pass | [TC-PP-04](./test-cases.md#tc-pp-04) |
| MLE-F-030 | Five classification algorithms | TC-MS-01 | Pass | [TC-MS-01](./test-cases.md#tc-ms-01) |
| MLE-F-031 | Three regression algorithms | TC-MS-02 | Pass | [TC-MS-02](./test-cases.md#tc-ms-02) |
| MLE-F-032 | Hyperparameter validation and defaults | TC-MS-03 | Pass | [TC-MS-03](./test-cases.md#tc-ms-03) |
| MLE-F-040 | Background execution without blocking the interface | TC-TR-01 | Pass | [TC-TR-01](./test-cases.md#tc-tr-01) |
| MLE-F-041 | Run states and useful failure reason | TC-TR-02 | Pass | [TC-TR-02](./test-cases.md#tc-tr-02) |
| MLE-F-042 | Reproduction from stored configuration and seed | TC-TR-03 | Pass | [TC-TR-03](./test-cases.md#tc-tr-03) |
| MLE-F-050 | Classification metrics and confusion matrix | TC-EV-01 | Pass | [TC-EV-01](./test-cases.md#tc-ev-01) |
| MLE-F-051 | Regression metrics | TC-EV-02 | Pass | [TC-EV-02](./test-cases.md#tc-ev-02) |
| MLE-F-052 | Comparison of completed runs | TC-EV-03 | Pass | [TC-EV-03](./test-cases.md#tc-ev-03) |
| MLE-F-060 | Downloadable evaluation report | TC-RP-01 | Pass | [TC-RP-01](./test-cases.md#tc-rp-01) |
| MLE-F-061 | CSV comparison export | TC-RP-02 | Pass | [TC-RP-02](./test-cases.md#tc-rp-02) |
| MLE-F-062 | Account listing and status management | TC-AD-01 | Pass | [TC-AD-01](./test-cases.md#tc-ad-01) |
| MLE-F-063 | Dataset catalogue listing and safe removal | TC-AD-02 | Pass | [TC-AD-02](./test-cases.md#tc-ad-02) |
| MLE-NF-001 | 95th-percentile response time at 10 concurrent users | TC-PERF-01 | Not Run | [TC-PERF-01](./test-cases.md#tc-perf-01); no load run recorded |
| MLE-NF-002 | 50,000 x 30 training duration within 120 seconds | TC-PERF-02 | Pass | [TC-PERF-02](./test-cases.md#tc-perf-02); five-run median 24.60 seconds |
| MLE-NF-003 | Failure isolation and application availability | TC-REL-01 | Pass | [TC-REL-01](./test-cases.md#tc-rel-01) |
| MLE-NF-004 | First-use timing and keyboard accessibility | TC-UX-01 | Not Run | [TC-UX-01](./test-cases.md#tc-ux-01); no participant evidence |
| MLE-NF-005 | At least 60% core-module line coverage | TC-MNT-01 | Not Run | [TC-MNT-01](./test-cases.md#tc-mnt-01); no coverage report |
| MLE-NF-006 | Run/audit retention and UTC timestamps | TC-OPS-01 | Pass | [TC-OPS-01](./test-cases.md#tc-ops-01) |
| MLE-SR-001 | HTTPS and TLS 1.2 or higher | TC-SEC-01 | Not Run | [TC-SEC-01](./test-cases.md#tc-sec-01); no deployed endpoint evidence |
| MLE-SR-002 | Salted password hashes and no raw-password logging | TC-SEC-02 | Pass | [TC-SEC-02](./test-cases.md#tc-sec-02) |
| MLE-SR-003 | Server-side ownership and role authorization | TC-SEC-03 | Pass | [TC-SEC-03](./test-cases.md#tc-sec-03) |
| MLE-SR-004 | Upload validation without pickle/joblib loading | TC-SEC-04 | Pass | [TC-SEC-04](./test-cases.md#tc-sec-04) |
| MLE-SR-005 | Per-run wall-clock limit and worker isolation | TC-SEC-05 | Pass | [TC-SEC-05](./test-cases.md#tc-sec-05) |
| MLE-SR-006 | Audited actions and append-only audit records | TC-SEC-06 | Pass | [TC-SEC-06](./test-cases.md#tc-sec-06) |

## Status summary

- Pass: 32 test cases
- Fail: 0 test cases
- Blocked: 0 test cases
- Not Run: 4 test cases (TC-PERF-01, TC-UX-01, TC-MNT-01, TC-SEC-01)

The full case objectives, preconditions, steps, expected and actual results,
and evidence references are in [test-cases.md](./test-cases.md).
