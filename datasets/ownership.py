"""Server-side dataset ownership (MLE-F-013 / MLE-SR-003).

One helper shared by every app that opens a dataset: an unknown id is a 404,
a dataset owned by someone else is a 403. Ownership is never taken from the
URL or the request body -- it is always compared against the signed-in user.
"""
from django.contrib.auth.decorators import login_required  # noqa: F401 (re-export for callers)
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from webui.models import Dataset


def get_owned_dataset(request, pk):
    """Return the request user's dataset ``pk``; 404 if unknown, 403 if not theirs."""
    dataset = get_object_or_404(Dataset, pk=pk)
    if dataset.owner_id != request.user.id:
        raise PermissionDenied
    return dataset
