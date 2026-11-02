# Audit Logging Verification

## Recorded events
- Successful login
- Failed login
- Successful user registration
- Successful dataset upload

Each event records the actor when known, action, resource, UTC-aware timestamp, outcome, and optional details.

## Append-only protection
- AuditLog rejects instance-level modifications and deletions.
- AuditLog rejects bulk QuerySet updates and deletions.
- Django admin exposes audit records as read-only.

## Deletion behavior
The current application has no dataset deletion endpoint, so deletion-event integration is pending an actual deletion action.

## Verification
Run:

    python -m pytest -v webui/test_audit.py

Then run the complete project test suite:

    python -m pytest -v