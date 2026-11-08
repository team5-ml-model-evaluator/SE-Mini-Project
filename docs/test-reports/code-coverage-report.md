
# Code Coverage Report

**Project:** Web Based ML Model Evaluator  
**Team:** Team 5  
**Coverage tool:** coverage.py 7.17.0  
**Measurement date:** 8 November 2026

## 1. Objective

Measure source-code line coverage for PipelineApp, ModelsApp and EvaluationApp against the SRS requirement MLE-NF-005.

The minimum required line coverage is 60% for each core component.

## 2. Line Coverage Results

| Source module | Covered statements | Total statements | Line coverage | Result |
|---|---:|---:|---:|---|
| pipeline/preprocessing.py | 220 | 275 | 80.0% | Pass |
| preprocessing/service.py | 94 | 100 | 94.0% | Pass |
| baseline_model.py | 74 | 84 | 88.1% | Pass |
| evaluation_metrics.py | 13 | 13 | 100.0% | Pass |

The two preprocessing implementation files have combined weighted line coverage of 83.7%.

## 3. Overall Results

- Total statements: 909
- Covered statements: 829
- Missing statements: 80
- Overall line coverage: 91.2%

## 4. Acceptance Criteria

MLE-NF-005 requires at least 60% line coverage for each core component.

All three core components exceed the required threshold.

**Overall result: PASS**

## 5. Evidence

- coverage.json
- coverage.xml
- coverage-execution.txt
- coverage-html/index.html

