# Unit Test Report

**Project:** Web Based ML Model Evaluator  
**Team:** Team 5  
**Report date:** 8 November 2026  
**Test environment:** Windows, Python 3.12, Django 5.2.18  
**Testing framework:** Pytest with pytest-django

## 1. Objective

The objective of unit testing is to verify that the individual application components behave according to their specified requirements and handle valid and invalid inputs correctly.

## 2. Test Execution

The following command was executed:

```powershell
python -m pytest tests webui datasets pipeline preprocessing -o "python_files=test_*.py *_tests.py tests.py" -m "not performance" -q --junitxml=docs/test-reports/unit-test-results.xml
```

## 3. Execution Summary

| Metric | Result |
|---|---:|
| Passed test cases | 369 |
| Passed subtests | 59 |
| Failed test cases | 0 |
| Errors | 0 |
| Deselected tests | 1 |
| Execution duration | 167.35 seconds |

The single deselected test was excluded by the performance-test marker filter and was handled separately through performance testing.

## 4. Result

All 369 collected test cases passed. An additional 59 subtests passed. No test failures or execution errors were reported.

**Overall unit-test result: PASS**

## 5. Evidence

- `unit-test-results.xml`
- `unit-test-execution.txt`
- `javascript-test-execution.txt`, where applicable
- `coverage-execution.txt`

## 6. Limitations

The unit-test execution does not independently establish successful live HTTPS/TLS deployment, concurrent-load performance, or human usability. These are assessed separately in the System Validation Report.

