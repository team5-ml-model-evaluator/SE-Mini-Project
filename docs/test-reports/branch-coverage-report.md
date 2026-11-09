
# Branch Coverage Report

**Project:** Web Based ML Model Evaluator  
**Team:** Team 5  
**Coverage tool:** coverage.py 7.17.0  
**Measurement date:** 8 November 2026

## 1. Objective

Measure execution of conditional branches in the application source code using coverage.py branch measurement.

## 2. Results

| Source module | Covered branches | Total branches | Branch coverage |
|---|---:|---:|---:|
| pipeline/preprocessing.py | 77 | 106 | 72.6% |
| preprocessing/service.py | 49 | 56 | 87.5% |
| baseline_model.py | 40 | 46 | 87.0% |
| evaluation_metrics.py | 8 | 8 | 100.0% |

## 3. Overall Results

- Total branches: 234
- Covered branches: 190
- Missing branches: 44
- Partially covered branch locations: 32
- Overall branch coverage: 81.2%

## 4. Interpretation

Branch coverage identifies conditional paths that were not executed during the automated test run.

The preprocessing implementation contains most of the remaining uncovered branches.

The Software Test Plan does not specify a minimum branch-coverage percentage. The measured value is reported for assessment and future improvement.

## 5. Conclusion

The branch-coverage measurement completed successfully.

**Measured branch coverage: 81.2%.**

## 6. Evidence

- coverage.json
- branch-coverage.txt
- coverage-execution.txt
- coverage-html/index.html
