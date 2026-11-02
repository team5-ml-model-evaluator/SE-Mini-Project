"""Dataset Catalogue Administration service (MLE-F-063, TC-AD-02).

Provides administrative listing and controlled removal of datasets from the catalogue.
Enforces administrative policy, ensures DB/file consistency, and prevents accidental
or unsafe deletion of datasets referenced by active/completed training runs.
"""
from __future__ import annotations

import os
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet
from django.http import Http404

from webui.models import Dataset
from .exceptions import DatasetAdminError, DatasetInUseError


def is_admin(user: Any) -> bool:
    """Return True if user is an active administrator (staff or superuser)."""
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def list_catalogue_datasets(user: Any = None) -> QuerySet[Dataset]:
    """Return all registered datasets for catalogue administration, newest first.

    If user is provided, validates that the user is an authorized administrator.
    """
    if user is not None and not is_admin(user):
        raise PermissionDenied("Only administrators can view the dataset catalogue.")

    return Dataset.objects.select_related("owner").order_by("-created_at")


def get_dataset_metadata(dataset: Dataset) -> dict[str, Any]:
    """Extract metadata for an individual dataset catalogue entry."""
    file_size_bytes = 0
    file_exists = False
    try:
        if dataset.file and hasattr(dataset.file, "path") and os.path.exists(dataset.file.path):
            file_size_bytes = os.path.getsize(dataset.file.path)
            file_exists = True
        elif dataset.file and hasattr(dataset.file, "size"):
            file_size_bytes = dataset.file.size
            file_exists = True
    except (OSError, ValueError):
        file_exists = False

    run_count = dataset.runs.count() if hasattr(dataset, "runs") else 0

    return {
        "id": dataset.id,
        "original_name": dataset.original_name,
        "owner": dataset.owner,
        "owner_username": dataset.owner.username if dataset.owner else "Unknown",
        "rows": dataset.rows,
        "column_count": dataset.column_count,
        "created_at": dataset.created_at,
        "file_size_bytes": file_size_bytes,
        "file_exists": file_exists,
        "run_count": run_count,
        "can_delete": run_count == 0,
    }


def delete_catalogue_dataset(pk: Any, user: Any) -> dict[str, Any]:
    """Safely remove a dataset catalogue entry and its stored file (MLE-F-063, TC-AD-02).

    Preconditions:
    - User must be an administrator (is_staff or is_superuser).
    - Dataset must exist (raises 404 if not found).
    - Dataset must not be referenced by existing training runs.

    Postconditions:
    - Database record is removed.
    - Underlying file on disk is removed cleanly (if present).
    - Returns summary dictionary of deleted dataset.
    """
    if not is_admin(user):
        raise PermissionDenied("Only administrators can remove dataset catalogue entries.")

    if isinstance(pk, Dataset):
        dataset = pk
    else:
        try:
            dataset = Dataset.objects.get(pk=pk)
        except (Dataset.DoesNotExist, ValidationError, ValueError):
            raise Http404(f"Dataset '{pk}' not found.")

    # Safety check: prevent deleting datasets referenced by existing training runs
    if hasattr(dataset, "runs") and dataset.runs.exists():
        run_count = dataset.runs.count()
        raise DatasetInUseError(
            f"Cannot remove dataset “{dataset.original_name}” because it is referenced by "
            f"{run_count} existing training run(s). Active runs and evaluation records must be preserved."
        )

    # Also check related objects from other models (e.g. RunsApp / webui.Run)
    for rel in dataset._meta.related_objects:
        accessor = rel.get_accessor_name()
        if accessor and ("run" in accessor.lower()):
            manager = getattr(dataset, accessor, None)
            if manager is not None and manager.exists():
                count = manager.count()
                raise DatasetInUseError(
                    f"Cannot remove dataset “{dataset.original_name}” because it is referenced by "
                    f"{count} existing training run(s). Active runs and evaluation records must be preserved."
                )

    meta = get_dataset_metadata(dataset)
    name = dataset.original_name

    # Determine file path before deleting model record
    file_path = None
    try:
        if dataset.file and hasattr(dataset.file, "path"):
            file_path = dataset.file.path
    except Exception:
        pass

    # 1. Delete database record
    dataset.delete()

    # 2. Maintain database / file consistency by deleting physical file
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            # Clean up parent directory if empty
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
        except OSError:
            # File system error should not invalidate successful database deletion
            pass

    return {
        "id": meta["id"],
        "original_name": name,
        "owner_username": meta["owner_username"],
        "deleted": True,
    }
