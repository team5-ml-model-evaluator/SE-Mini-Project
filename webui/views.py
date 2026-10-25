import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ModelForm, PipelineForm, UploadForm, error_summary
from .models import Dataset
from .stages import stage_list
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
