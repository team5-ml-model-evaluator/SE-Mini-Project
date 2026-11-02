# MLE-2: administrator account management and retention

## Administrator workflow

Users in the existing `Admin` group, and superusers as permitted by the existing
`role_required("Admin")` policy, can open the administrator dashboard. The dashboard
summarizes registered, active, and deactivated users, datasets, model runs, run batches,
and audit events. Its links lead to account management and the dataset catalogue.

The account list can be searched by username or email. An administrator can deactivate
another non-superuser account or reactivate a deactivated account. These actions are
POST-only forms with CSRF tokens. The endpoint repeats the role check server-side, rejects
unknown actions and missing accounts, prevents self-deactivation, and does not permit
status changes to superuser accounts. It never deletes users.

Status is stored in Django's existing `User.is_active` field. Django's authentication
backend rejects inactive users both at login and when resolving an authenticated session,
so changing the field also invalidates existing sessions on their next request. Reactivation
restores the ability to authenticate.

## Authorization and audit

All administrator pages and account status changes use the existing `Admin` role utility;
ordinary authenticated users receive HTTP 403. A status change is performed in a database
transaction and recorded through `webui.audit.record_audit` as
`account_deactivated` or `account_reactivated`, with the acting administrator, target
`user:<id>`, success outcome, and the audit model's UTC timestamp. Audit details contain
only the target username. Passwords, session identifiers, and authentication secrets are
not recorded.

The existing append-only `AuditLog` protections and read-only Django admin integration are
unchanged. Its actor foreign key uses `SET_NULL`, so an audit event remains when its actor
account is eventually removed.

## Data retention and privacy

Dataset ownership, run ownership, batch ownership, run-to-dataset, and batch-to-dataset
foreign keys use `PROTECT`. The separate `TrainingJob` history also protects its user
foreign key. Deleting a user or dataset that is referenced by these records therefore
fails instead of cascading through the dataset or completed training history. Run-to-batch
remains `SET_NULL` so the existing optional-batch relationship is preserved. No automatic
purge job is introduced.

The administrator dataset catalogue exposes only the dataset name, owner, row and column
counts, and upload time. It does not link to uploaded files or display CSV contents. Dataset
and audit timestamps use the existing timezone-aware fields with `USE_TZ = True` and the
project's UTC timezone.

## SRS and design notes

The issue tracks audit logging separately, but this implementation includes account-status
events because the MLE-2 task explicitly requires them and the project already provides an
append-only audit service. The existing authorization policy permits both Admin-group
members and superusers to enter administrator views; superuser status itself is protected
from changes through this interface. The standard Django `is_active` field is used rather
than introducing a second account-status field or a custom authentication backend.
