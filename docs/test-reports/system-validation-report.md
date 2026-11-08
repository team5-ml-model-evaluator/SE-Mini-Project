### TC-PERF-002 — Model Training Performance

**Requirement:** MLE-NF-002

**Test description:** Execute five training runs against the 50,000-row × 30-column benchmark dataset.

**Execution results:**

| Run | Execution time |
|---|---:|
| 1 | 19.74 seconds |
| 2 | 31.43 seconds |
| 3 | 29.05 seconds |
| 4 | 28.07 seconds |
| 5 | 26.11 seconds |

**Median execution time:** 28.07 seconds

**Acceptance threshold:** Median ≤ 120 seconds.

**Actual result:** 28.07 seconds.

**Status: PASS**

**Evidence:** `docs/test-reports/tc-perf-002.txt`

**Test execution:** 1 passed.
