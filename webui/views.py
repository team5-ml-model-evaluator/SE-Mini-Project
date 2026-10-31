import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from .comparison import build_comparison
from .matrices import matrix_window
from .target_validation import validate_classification_target
from .forms import ComparisonForm, ModelForm, PipelineForm, UploadForm, error_summary
from .models import Dataset, Run
from .reporting import build_report, comparison_csv, report_pdf
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
    form = ModelForm(request.POST if posted else None, initial={"algorithm": draft.get("algorithm", "")},
                     dataset=dataset, target=draft["target_column"])
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
    try:
        validate_classification_target(dataset, draft.get("target_column"), draft["algorithm"])
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
        return redirect("model_step", pk=dataset.id)
    job_key = runs.start(request.user, dataset, _run_config(dataset, draft))
    return redirect("run_detail", job_key=job_key)


def _owned_run(request, job_key):
    run = get_object_or_404(Run.objects.defer("result"), job_key=job_key)
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
    window = matrix_window(result, request.GET.get("matrix_row", 1), request.GET.get("matrix_col", 1))
    return _page(
        request, "run.html", stage, run=run, status=status, clock=_clock(status["elapsed_s"]),
        result=result, matrix=window["rows"], labels=window["labels"], matrix_window=window,
        algorithm=BY_KEY[run.run_config["algorithm"]],
        active=run.state in (Run.QUEUED, Run.RUNNING),
    )


@require_GET
def run_status(request, job_key):
    """GET /api/runs/<job_key>/status (SAD interface 1). 401 signed out, 403 someone else's run, 404 unknown."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in to see this run."}, status=401)
    run = Run.objects.defer("result", "run_config").filter(job_key=job_key).first()
    if run is None:
        return JsonResponse({"error": "There is no run with this key."}, status=404)
    if run.owner_id != request.user.id:
        return JsonResponse({"error": "This run belongs to another user."}, status=403)
    response = JsonResponse(runs.get_status(run))
    response["Cache-Control"] = "no-store"
    return response


def _comparison_selection(request, dataset, submitted):
    form = ComparisonForm(request.GET if submitted else None, owner=request.user, dataset=dataset)
    comparison = None
    if submitted and form.is_valid():
        by_key = {run.job_key: run for run in form.cleaned_data["runs"]}
        # Keep the submitted column order and remove repeated keys.
        selected = [by_key[key] for key in dict.fromkeys(request.GET.getlist("runs"))]
        try:
            comparison = build_comparison(selected)
        except ValidationError as exc:
            form.add_error("runs", exc)
    return form, comparison


@login_required
@require_GET
def run_comparison(request, pk):
    dataset = _owned_dataset(request, pk)
    submitted = "compare" in request.GET or "runs" in request.GET
    form, comparison = _comparison_selection(request, dataset, submitted)
    return _page(request, "comparison.html", "results", dataset=dataset, form=form,
                 comparison=comparison, has_runs=form.fields["runs"].queryset.exists())


def _download(content, content_type, filename):
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response



@login_required
@require_GET
def run_report(request, job_key, format):
    if format not in {"html", "pdf"}:
        raise Http404
    run = _owned_run(request, job_key)
    _owned_dataset(request, run.dataset_id)
    try:
        report = build_report(run, detailed=request.GET.get("details") == "1")
    except ValidationError as exc:
        return HttpResponse(" ".join(exc.messages), status=409, content_type="text/plain; charset=utf-8")
    variant = "-technical" if report["detailed"] else ""
    filename = f"evaluation-{run.pk}{variant}.{format}"
    if format == "pdf":
        return _download(report_pdf(report), "application/pdf", filename)
    html = render_to_string("webui/report.html", {"report": report})
    response = _download(html, "text/html; charset=utf-8", filename)
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return response



@login_required
@require_GET
def run_comparison_csv(request, pk):
    dataset = _owned_dataset(request, pk)
    form, comparison = _comparison_selection(request, dataset, True)
    if comparison is None:
        response = _page(request, "comparison.html", "results", dataset=dataset, form=form,
                         comparison=None, has_runs=form.fields["runs"].queryset.exists())
        response.status_code = 400
        return response
    return _download(comparison_csv(comparison), "text/csv; charset=utf-8", f"comparison-{dataset.id}.csv")
