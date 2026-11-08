# Test Summary Report

**Project:** Web Based ML Model Evaluator  
**Team:** Team 5  
**Report date:** 8 November 2026  
**Scope:** Automated functional and non-functional validation for the current branch and test configuration.

## 1. Test execution summary

The non-performance automated suite was executed with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests webui datasets pipeline preprocessing -o "python_files=test_*.py *_tests.py tests.py" -m "not performance" -q --junitxml=docs/test-reports/unit-test-results.xml --cov=. --cov-branch --cov-report=json:docs/test-reports/coverage.json --cov-report=xml:docs/test-reports/coverage.xml --cov-report=html:docs/test-reports/coverage-html
```

### Result

| Metric | Value |
|---|---:|
| Passed tests | 369 |
| Failed tests | 0 |
| Errors | 0 |
| Skipped tests | 0 |
| Deselected tests | 1 |
| Passed subtests | 59 |
| Execution time | 214.95 seconds |

The one deselected test was excluded by the `performance` marker, which is intentional for the non-performance validation run.

## 2. Coverage summary

The generated coverage data was taken from `docs/test-reports/coverage.json`.

### Line coverage for required application modules

| Application module | Covered statements | Total statements | Coverage |
|---|---:|---:|---:|
| `pipeline/preprocessing.py` | 220 | 275 | 80.0% |
| `preprocessing/service.py` | 94 | 100 | 94.0% |
| `baseline_model.py` | 74 | 84 | 88.1% |
| `evaluation_metrics.py` | 13 | 13 | 100.0% |

All required application modules exceeded the SRS minimum of 60% line coverage.

### Overall project coverage

- Total measured statements: 4,920
- Covered statements: 4,664
- Overall line coverage: 93.3%
- Branch coverage (measured for tracked branch paths): 84.9%

The project-level branch measurement indicates that most tested paths executed successfully, while conditional branches in preprocessing still account for a significant portion of the remaining uncovered logic.

## 3. Performance validation summary

### TC-PERF-001: Concurrent response-time check

Status: Incomplete verification.

Evidence reviewed:
- Locust CSV and request statistics under `docs/test-reports/`
- Request count and aggregate p95 values

The request statistics showed low response times and no failures, but the evidence available in the repository does not confirm the full 5-minute duration and 10-user concurrency conditions specified by the SRS. Because the full load-test conditions were not sufficiently evidenced, this case should be recorded as incomplete rather than fully passed.

### TC-PERF-002: Training benchmark

Status: Pass.

Recorded benchmark values:
- 19.74 s
- 31.43 s
- 29.05 s
- 28.07 s
- 26.11 s

Median: 28.07 seconds.

This is below the SRS threshold of 120 seconds for the specified benchmark dataset, so the recorded performance requirement is satisfied.

## 4. Requirements verification status

The updated traceability matrix and test-case documentation indicate the following high-level status:

- Functional test groups: mostly pass
- Security and access-control checks: pass where evidence exists
- Performance benchmark: pass for training time; concurrent-load test remains incomplete
- Usability and deployment verification: not yet fully evidenced
- Coverage requirement MLE-NF-005: satisfied for the required application areas

## 5. Conclusion

The repository demonstrates strong automated verification for the current implementation: the non-performance pytest suite passed, the core application modules exceed the minimum coverage thresholds, and the training benchmark requirement was met. The main outstanding validation item is the complete concurrent-load performance run, which needs full duration and concurrency evidence to be treated as fully validated.

## 6. Supporting evidence

- `docs/test-reports/unit-test-results.xml`
- `docs/test-reports/coverage.json`
- `docs/test-reports/coverage.xml`
- `docs/test-reports/coverage-html/index.html`
- `docs/test-reports/unit-test-report.md`
- `docs/test-reports/code-coverage-report.md`
- `docs/test-reports/branch-coverage-report.md`
- `docs/test-reports/system-validation-report.md`
- `docs/test-cases.md`
- `docs/requirements-traceability-matrix.md`
