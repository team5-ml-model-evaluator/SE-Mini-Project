import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone

from webui.models import AuditLog
from webui.admin import AuditLogAdmin


@pytest.mark.django_db
def test_audit_record_stores_required_fields(django_user_model):
    user = django_user_model.objects.create_user(
        username="audit_test",
        password="test-password-123",
    )
    event = AuditLog.objects.create(
        actor=user,
        action="dataset_upload",
        resource="dataset-123",
        outcome="success",
    )

    assert event.actor == user
    assert event.action == "dataset_upload"
    assert event.resource == "dataset-123"
    assert event.outcome == "success"
    assert timezone.is_aware(event.timestamp)
    assert event.timestamp.utcoffset().total_seconds() == 0


@pytest.mark.django_db
def test_audit_record_cannot_be_modified(django_user_model):
    user = django_user_model.objects.create_user(
        username="audit_edit_test",
        password="test-password-123",
    )
    event = AuditLog.objects.create(
        actor=user,
        action="login",
        resource="user",
        outcome="success",
    )

    event.action = "changed"
    with pytest.raises(ValueError, match="cannot be modified"):
        event.save()


@pytest.mark.django_db
def test_audit_record_cannot_be_deleted(django_user_model):
    user = django_user_model.objects.create_user(
        username="audit_delete_test",
        password="test-password-123",
    )
    event = AuditLog.objects.create(
        actor=user,
        action="login",
        resource="user",
        outcome="success",
    )

    with pytest.raises(ValueError, match="cannot be deleted"):
        event.delete()

    assert AuditLog.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_audit_records_reject_bulk_modification_and_deletion(django_user_model):
    user = django_user_model.objects.create_user(
        username="audit_bulk_test",
        password="test-password-123",
    )
    event = AuditLog.objects.create(
        actor=user,
        action="login",
        resource="user",
        outcome="success",
    )

    with pytest.raises(ValueError, match="cannot be modified"):
        AuditLog.objects.filter(pk=event.pk).update(outcome="failure")

    with pytest.raises(ValueError, match="cannot be deleted"):
        AuditLog.objects.filter(pk=event.pk).delete()

    assert AuditLog.objects.filter(pk=event.pk, outcome="success").exists()


@pytest.mark.django_db
def test_audit_admin_disables_add_change_and_delete():
    model_admin = AuditLogAdmin(AuditLog, admin.site)
    request = RequestFactory().get("/admin/webui/auditlog/")

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False