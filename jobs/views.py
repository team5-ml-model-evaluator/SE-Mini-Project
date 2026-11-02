
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
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
    """List only training jobs owned by the current user."""
    jobs = TrainingJob.objects.filter(user=request.user)

    return render(
        request,
        "jobs/job_list.html",
        {"jobs": jobs},
    )


@login_required
@require_http_methods(["GET"])
def training_job_status(request, job_id):
    """Return status details for a job owned by the current user."""
    job = get_object_or_404(
        TrainingJob,
        id=job_id,
        user=request.user,
    )

    return JsonResponse(
        {
            "id": str(job.id),
            "status": job.status,
            "status_display": job.get_status_display(),
            "dataset_name": job.dataset_name,
            "model_name": job.model_name,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "started_at": (
                job.started_at.isoformat() if job.started_at else None
            ),
            "finished_at": (
                job.finished_at.isoformat() if job.finished_at else None
            ),
            "error_message": (
                job.error_message
                if job.status == TrainingJob.Status.FAILED
                else ""
            ),
        }
    )
