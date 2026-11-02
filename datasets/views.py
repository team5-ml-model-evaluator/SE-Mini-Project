"""Views for Dataset Catalogue Administration (MLE-F-063, TC-AD-02)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from .catalogue import (
    delete_catalogue_dataset,
    get_dataset_metadata,
    is_admin,
    list_catalogue_datasets,
)
from .exceptions import DatasetInUseError


@login_required
def catalogue_list(request):
    """Administrator catalogue view listing all datasets with metadata (MLE-F-063)."""
    if not is_admin(request.user):
        raise PermissionDenied("You do not have administrative privileges to access the dataset catalogue.")

    datasets = list_catalogue_datasets(request.user)
    entries = [get_dataset_metadata(d) for d in datasets]

    return render(
        request,
        "datasets/catalogue.html",
        {
            "datasets": entries,
            "total_count": len(entries),
        },
    )


@login_required
def catalogue_delete(request, pk):
    """CSRF-protected POST endpoint to remove a dataset catalogue entry (TC-AD-02)."""
    if not is_admin(request.user):
        raise PermissionDenied("You do not have administrative privileges to remove dataset catalogue entries.")

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"], "Destructive actions must use POST.")

    try:
        result = delete_catalogue_dataset(pk, user=request.user)
        messages.success(request, f"Dataset “{result['original_name']}” was removed from the catalogue.")
    except DatasetInUseError as exc:
        messages.error(request, str(exc))

    return redirect("catalogue_list")
