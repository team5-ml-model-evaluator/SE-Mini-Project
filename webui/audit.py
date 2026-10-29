"""Helpers for recording security-relevant application events."""

from .models import AuditLog


def record_audit(actor, action, resource, outcome, details=None):
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        resource=str(resource),
        outcome=outcome,
        details=details or {},
    )