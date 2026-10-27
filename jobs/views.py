
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import TrainingJobForm
from .models import TrainingJob


@login_required
@require_http_methods(["GET", "POST"])
def create_training_job(request):
    """Create a queued training job for the authenticated user."""

    if request.method == "POST":
        form = TrainingJobForm(request.POST)

        if form.is_valid():
            job = TrainingJob.objects.create(
                user=request.user,
                dataset_name=form.cleaned_data["dataset_name"],
                model_name=form.cleaned_data["model_name"],
                configuration=form.cleaned_data["configuration"],
            )

            return render(
                request,
                "jobs/job_created.html",
                {"job": job},
            )
    else:
        form = TrainingJobForm()

    return render(
        request,
        "jobs/job_form.html",
        {"form": form},
    )


@login_required
@require_http_methods(["GET"])
def list_training_jobs(request):
    """List only the training jobs owned by the current user."""

    jobs = TrainingJob.objects.filter(user=request.user)

    return render(
        request,
        "jobs/job_list.html",
        {"jobs": jobs},
    )
