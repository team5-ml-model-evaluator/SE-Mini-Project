"""Dataset profiling (MLE-F-012).

Turns a CSV upload or a stored :class:`webui.models.Dataset` into the profile
dict the WebUI stores on ``Dataset.profile`` and the ``pandas.DataFrame`` the
downstream preprocessing uses. The returned shape is fixed by PR #27:

    {"rows": int, "column_count": int,
     "columns": [{"name", "dtype", "missing_count", "missing_pct"}]}

``dtype`` labels stay on the same three values the WebUI renders (``integer``,
``decimal``, ``text``) so templates and tests keep working unchanged.
"""
import io
from pathlib import Path

import pandas as pd

MISSING_TOKENS = {"", "na", "n/a", "nan", "null", "none"}


class ProfileError(Exception):
    """A stored dataset could not be read back into a frame."""


def _dtype_label(values):
    """integer if every present value parses as int, else decimal if float, else text."""
    present = [v for v in values if v.strip().lower() not in MISSING_TOKENS]
    if not present:
        return "text"
    for caster, label in ((int, "integer"), (float, "decimal")):
        try:
            for value in present:
                caster(value)
            return label
        except ValueError:
            continue
    return "text"


def _read_text_frame(text):
    """Read CSV text keeping every cell as its exact string (empty stays empty).

    Loading as ``str`` with NA filtering off means the profile is computed from
    the literal uploaded tokens, matching the WebUI's column checks.
    """
    return pd.read_csv(io.StringIO(text, newline=""), dtype=str, keep_default_na=False)


def profile_dataframe(df):
    """Profile an already-loaded string frame into the WebUI's profile shape."""
    n_rows = int(df.shape[0])
    columns = []
    for name in df.columns:
        values = [str(v) for v in df[name].tolist()]
        missing = sum(1 for v in values if v.strip().lower() in MISSING_TOKENS)
        columns.append(
            {
                "name": str(name),
                "dtype": _dtype_label(values),
                "missing_count": missing,
                "missing_pct": round(100 * missing / n_rows, 1) if n_rows else 0.0,
            }
        )
    return {"rows": n_rows, "column_count": len(df.columns), "columns": columns}


def profile_text(text):
    """Profile raw CSV text (already validated) into the WebUI's profile shape."""
    return profile_dataframe(_read_text_frame(text))


def load_dataframe(dataset):
    """Read a stored :class:`webui.models.Dataset` back into a typed DataFrame.

    Used by the preprocessing service, which needs real numeric dtypes rather
    than the all-string frame the profile is computed from.
    """
    if not dataset.file.name:
        raise ProfileError("The stored dataset file could not be found.")
    path = Path(dataset.file.path)
    if not path.exists():
        raise ProfileError("The stored dataset file could not be found.")
    try:
        return pd.read_csv(path)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ProfileError(f"The stored dataset could not be read: {exc}") from exc
