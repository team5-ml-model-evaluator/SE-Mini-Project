"""Missing-value / feature-matrix configuration step for a dataset (MLE-F-020, MLE-F-021)."""
import pandas as pd
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from datasets.ownership import get_owned_dataset
from datasets.profiling import ProfileError, load_dataframe

from .exceptions import PreprocessingError
from .forms import PreprocessingForm
from .models import PreprocessingConfig
from .service import Preprocessor


def _preview(X, y):
    head = X.head(10)
    return {
        "n_rows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_names": [str(c) for c in X.columns],
        "columns": [str(c) for c in head.columns],
        "rows": [[("" if pd.isna(v) else v) for v in row] for row in head.itertuples(index=False)],
        "target_name": str(y.name),
        "target_nonnull": int(y.notna().sum()),
    }


def _context(dataset, **extra):
    context = {"dataset": dataset}
    context.update(extra)
    return context


@login_required
def configure(request, pk):
    dataset = get_owned_dataset(request, pk)
    try:
        df = load_dataframe(dataset)
    except ProfileError as exc:
        return render(
            request,
            "preprocessing/configure.html",
            _context(dataset, columns=[], form=None, strategy_rows=[], error=f"Cannot load dataset: {exc}"),
        )

    columns = list(df.columns)
    form = PreprocessingForm(request.POST or None, columns=columns)
    strategy_rows = [(col, form[f"strategy_{i}"]) for i, col in enumerate(columns)]

    saved_config = None
    preview = None
    error = None

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        strategies = data["_strategies"]
        try:
            pre = Preprocessor(df, data["target"], data["_features"], strategies)
            X, y = pre.fit_transform(df)
        except PreprocessingError as exc:
            error = str(exc)
        else:
            saved_config = PreprocessingConfig.objects.create(
                dataset=dataset,
                created_by=request.user,
                target_column=data["target"],
                feature_columns=data["_features"],
                excluded_columns=data["_excluded"],
                missing_strategies=strategies,
            )
            preview = _preview(X, y)

    existing = PreprocessingConfig.objects.filter(dataset=dataset, created_by=request.user)
    return render(
        request,
        "preprocessing/configure.html",
        _context(
            dataset,
            columns=columns,
            form=form,
            strategy_rows=strategy_rows,
            saved_config=saved_config,
            preview=preview,
            error=error,
            existing_configs=existing,
        ),
    )
