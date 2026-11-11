# Security Requirements Verification

## Overview

This document records the verification evidence for Security Requirements SR-001 to SR-006. Verification is based on automated tests, configuration inspection and implementation evidence.

**Security test execution:** 87 passed, 13 subtests passed, 1 warning.

**Full test suite:** 228 passed, 1 warning.

## SR-001 — HTTPS and TLS Enforcement

**Test Case:** TC-SEC-01  
**Status:** Partially Verified

- HTTPS redirect configuration is present in the Django security settings.
- Automated tests for HTTPS redirection and production security settings passed.
- Actual deployed-host TLS 1.2+ support has not been independently verified.

**Evidence:** Security test report and `config/settings.py`.

## SR-002 — Password and Credential Protection

**Test Case:** TC-SEC-02  
**Status:** Partially Verified

- Authentication tests confirm that registered passwords are validated using Django's password-checking mechanism.
- Login success and failure are recorded through audit logging.
- Explicit verification that logs never contain credential material has not been independently performed.

**Evidence:** `tests/test_authentication.py`, `config/auth_views.py`.

## SR-003 — Access Control and Resource Ownership

**Test Case:** TC-SEC-03  
**Status:** Passed

- Authentication is required for protected operations.
- Role-based access restrictions are tested.
- Cross-user access to training runs is tested and returns HTTP 403.
- Unauthorized users cannot create or access another user's protected resources.

**Evidence:** Authentication, training-job, run-access and target-validation security tests.

## SR-004 — Secure Dataset Upload and Validation

**Test Case:** TC-SEC-04  
**Status:** Partially Verified

- CSV extension validation is implemented.
- A maximum upload size of 50 MB is configured.
- Structural validation is performed on raw CSV text before profiling.
- No direct `pickle.load` or `joblib.load` usage was found in the inspected Python files.
- Complete verification of crafted-file rejection and all parsed-structure checks has not been established.

**Evidence:** `datasets/validation.py`, `config/settings.py`, dataset validation implementation.

## SR-005 — Training Job Isolation and Resource Limits

**Test Case:** TC-SEC-05  
**Status:** Partially Verified

- Training jobs execute in separate worker processes.
- A configurable wall-clock timeout is implemented, with a default of 600 seconds.
- Timeout handling terminates the affected worker and marks its run as failed.
- The dataset-size limit and its enforcement have not been independently verified.

**Evidence:** `webui/standins/runs.py`, `config/settings.py`, training worker tests.

## SR-006 — Audit Logging and Immutability

**Test Case:** TC-SEC-06  
**Status:** Passed

- Audit records capture actor, action, resource and outcome information.
- Audit timestamps are recorded.
- Tests verify that audit records cannot be modified or deleted through the tested model operations.
- Administrative audit behavior and audit-history preservation are tested.

**Evidence:** `webui/models.py`, `webui/audit.py`, audit and administration security tests.

## Verification Summary

| Requirement | Result |
|---|---|
| SR-001 — HTTPS/TLS | Partially Verified |
| SR-002 — Password Security | Partially Verified |
| SR-003 — Access Control | Passed |
| SR-004 — Upload Security | Partially Verified |
| SR-005 — Job Isolation and Limits | Partially Verified |
| SR-006 — Audit Logging | Passed |

**Overall:** Automated security tests passed. Requirements marked Partially Verified have specific deployment-level or implementation-level evidence gaps that have not been independently confirmed. These results should not be interpreted as full acceptance of every security requirement.
