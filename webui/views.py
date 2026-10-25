import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import ModelForm, PipelineForm, UploadForm, error_summary
from .models import Dataset, Run
from .stages import stage_list
from .standins import runs
from .standins.catalogue import BY_KEY


def _owned_dataset(request, pk):
    """404 for an unknown id, 403 when the dataset belongs to someone else (MLE-F-013 / MLE-SR-003)."""
    dataset = get_object_or_404(Dataset, pk=pk)
    if dataset.owner_id != request.user.id:
        raise PermissionDenied
    return dataset


def _draft_key(dataset):
    return f"draft-{dataset.id}"


def _page(request, template, stage, **context):
    context.update(stages=stage_list(stage), stage=stage)
    return render(request, f"webui/{template}", context)


@login_required
def dataset_list(request):
    return _page(request, "dataset_list.html", "dataset", datasets=request.user.datasets.all())


@login_required
def dataset_new(request):
    posted = request.method == "POST"
    form = UploadForm(request.POST, request.FILES) if posted else UploadForm()
    if posted and form.is_valid():
        uploaded = form.cleaned_data["file"]
        dataset = Dataset(
            owner=request.user,
            original_name=os.path.basename(uploaded.name)[:255],
            file=uploaded,
            rows=form.profile["rows"],
            column_count=form.profile["column_count"],
            profile=form.profile,
        )
        dataset.save()
        messages.success(request, f"“{dataset.original_name}” was uploaded.")
        return redirect("dataset_detail", pk=dataset.id)
    return _page(request, "upload.html", "dataset", form=form, errors=error_summary(form) if form.errors else [])


@login_required
def dataset_detail(request, pk):
    dataset = _owned_dataset(request, pk)
    return _page(request, "dataset_detail.html", "dataset", dataset=dataset)


@login_required
def pipeline_step(request, pk):
    dataset = _owned_dataset(request, pk)
    draft = request.session.get(_draft_key(dataset), {})
    initial = {"target": draft.get("target_column", "")}
    for i, name in enumerate(dataset.column_names):
        if name in draft.get("excluded_columns", []):
            initial[f"role_{i}"] = "excluded"
    posted = request.method == "POST"
    form = PipelineForm(dataset.column_names, request.POST if posted else None, initial=initial)
    if posted and form.is_valid():
        draft.update(
            target_column=form.cleaned_data["target"],
            feature_columns=form.cleaned_data["feature_columns"],
            excluded_columns=form.cleaned_data["excluded_columns"],
        )
        request.session[_draft_key(dataset)] = draft
        return redirect("model_step", pk=dataset.id)
    return _page(
        request, "pipeline.html", "pipeline", dataset=dataset, form=form,
        errors=error_summary(form) if form.errors else [],
    )


@login_required
def model_step(request, pk):
    dataset = _owned_dataset(request, pk)
    draft = request.session.get(_draft_key(dataset))
    if not draft or "target_column" not in draft:
        messages.error(request, "Choose the target and feature columns before choosing a model.")
        return redirect("pipeline_step", pk=dataset.id)
    posted = request.method == "POST"
    form = ModelForm(request.POST if posted else None, initial={"algorithm": draft.get("algorithm", "")})
    if posted and form.is_valid():
        draft["algorithm"] = form.cleaned_data["algorithm"]
        request.session[_draft_key(dataset)] = draft
        return redirect("settings_summary", pk=dataset.id)
    return _page(
        request, "model.html", "model", dataset=dataset, draft=draft, form=form,
        errors=error_summary(form) if form.errors else [],
    )


@login_required
def settings_summary(request, pk):
    dataset = _owned_dataset(request, pk)
    draft = request.session.get(_draft_key(dataset))
    if not draft or "algorithm" not in draft:
        messages.error(request, "Choose an algorithm before reviewing the settings.")
        return redirect("model_step", pk=dataset.id)
    return _page(
        request, "summary.html", "model", dataset=dataset, draft=draft, algorithm=BY_KEY[draft["algorithm"]]
    )


def _run_config(dataset, draft):
    """The run_config of SAD interface 2. Preprocessing settings are not collected yet, so they stay empty."""
    return {
        "dataset_id": str(dataset.id),
        "target_column": draft["target_column"],
        "feature_columns": draft["feature_columns"],
        "imputation": None,
        "encoding": None,
        "scaling": None,
        "split_ratio": 0.8,
        "random_seed": 42,
        "algorithm": draft["algorithm"],
        "hyperparameters": {},
    }


@login_required
@require_POST
def start_run(request, pk):
    """Start a run from the saved settings and return to the user straight away (MLE-F-040)."""
    dataset = _owned_dataset(request, pk)
    draft = request.session.get(_draft_key(dataset))
    if not draft or "algorithm" not in draft:
        messages.error(request, "Choose an algorithm before starting a run.")
        return redirect("model_step", pk=dataset.id)
    job_key = runs.start(request.user, dataset, _run_config(dataset, draft))
    return redirect("run_detail", job_key=job_key)


def _owned_run(request, job_key):
    run = get_object_or_404(Run, job_key=job_key)
    if run.owner_id != request.user.id:
        raise PermissionDenied
    return run


def _clock(seconds):
    """Elapsed time as mm:ss, the same format run.js uses while the page is live."""
    if seconds is None:
        return "00:00"
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


@login_required
@require_GET
def run_detail(request, job_key):
    run = _owned_run(request, job_key)
    status = runs.get_status(run)
    run.refresh_from_db()
    stage = "results" if run.state == Run.COMPLETED else "run"
    result = run.result or {}
    labels = result.get("labels") or []
    matrix = []
    for i, row in enumerate(result.get("confusion_matrix") or []):
        matrix.append({"label": labels[i] if i < len(labels) else str(i), "cells": [
            {"value": value, "correct": j == i} for j, value in enumerate(row)]})
    return _page(
        request, "run.html", stage, run=run, status=status, clock=_clock(status["elapsed_s"]),
        result=result, matrix=matrix, labels=labels,
        algorithm=BY_KEY[run.run_config["algorithm"]],
        active=run.state in (Run.QUEUED, Run.RUNNING),
    )


@require_GET
def run_status(request, job_key):
    """GET /api/runs/<job_key>/status (SAD interface 1). 401 signed out, 403 someone else's run, 404 unknown."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in to see this run."}, status=401)
    run = Run.objects.filter(job_key=job_key).first()
    if run is None:
        return JsonResponse({"error": "There is no run with this key."}, status=404)
    if run.owner_id != request.user.id:
        return JsonResponse({"error": "This run belongs to another user."}, status=403)
    response = JsonResponse(runs.get_status(run))
    response["Cache-Control"] = "no-store"
    return response
