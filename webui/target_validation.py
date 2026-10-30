"""Preflight checks for an accidental numeric-amount classification target."""
import pandas as pd
from django.core.exceptions import ValidationError

from .standins.catalogue import BY_KEY


def validate_classification_target(dataset, target, algorithm_key):
    """Reject likely amounts, while allowing numeric category codes and text classes.

    This is a usability heuristic, not a definitive inference of the problem type:
    flag numeric targets with more than 20 distinct values AND over half of rows
    distinct. Numeric binary/multiclass codes and repeated text classes stay valid.
    Recheck at submission so an old draft cannot bypass the form validation.
    """
    algorithm = BY_KEY.get(algorithm_key)
    if algorithm is None or algorithm.task != "classification":
        return
    try:
        with dataset.file.open("rb") as handle:
            values = pd.read_csv(handle, usecols=[target], dtype=str)[target].dropna().str.strip()
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValidationError(
            "Could not check the target column. Upload the CSV again and choose its target column."
        ) from exc
    values = values[values != ""]
    if values.empty:
        return  # The training worker already explains missing or single-valued targets.
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.isna().any():
        return  # Non-numeric labels are valid categories, even with many classes.
    distinct = numeric.nunique()
    if distinct > 20 and distinct > len(numeric) / 2:
        raise ValidationError(
            f"Target '{target}' has {distinct} distinct values in {len(numeric)} rows and looks like a numeric amount. "
            "Classification predicts categories, not amounts. Choose a regression algorithm such as Linear "
            "Regression, or change the target to a categorical column such as a yes/no outcome."
        )
