"""Preprocessing service for target/feature selection and missing-value handling.

MLE-F-020 (target/features) and MLE-F-021 (missing values).

Design notes for later integration
----------------------------------
* ``Preprocessor`` follows a fit/transform contract so that, when train/test
  splitting is added by another component, transformation statistics (mean /
  median / mode) are fit on the *training* data only and reused for any other
  frame via ``transform`` -- i.e. no leakage from held-out data.
* ``transform`` always operates on a copy, so the original uploaded dataframe is
  never modified.
* Invalid strategy/type combinations raise ``PreprocessingError`` instead of
  silently falling back to a different strategy.
"""

import pandas as pd

from .exceptions import PreprocessingError
from .models import MissingStrategy

_VALID_STRATEGIES = {c.value for c in MissingStrategy}
_IMPUTE_STRATEGIES = {MissingStrategy.MEAN, MissingStrategy.MEDIAN, MissingStrategy.MODE}


def is_numeric_column(df: pd.DataFrame, column: str) -> bool:
    return pd.api.types.is_numeric_dtype(df[column])


def validate_selection(all_columns, target, features):
    """Validate a target/feature selection against ``all_columns``.

    Returns ``(features, excluded)``. Raises ``PreprocessingError`` when the
    selection is invalid.
    """
    all_columns = list(all_columns)
    target = str(target) if target is not None else None

    if target is None or target == "":
        raise PreprocessingError("A target column must be selected.")
    if target not in all_columns:
        raise PreprocessingError(f"Target column '{target}' does not exist in the dataset.")

    features = [str(c) for c in (features or [])]
    # Preserve dataset column order, reject duplicates and unknown names.
    seen = set()
    ordered = []
    for col in all_columns:
        if col in features:
            if col in seen:
                raise PreprocessingError(f"Feature column '{col}' is listed more than once.")
            seen.add(col)
            ordered.append(col)
    for col in features:
        if col not in all_columns:
            raise PreprocessingError(f"Feature column '{col}' does not exist in the dataset.")

    if target in features:
        raise PreprocessingError("The target column cannot also be a feature column.")
    if not ordered:
        raise PreprocessingError("At least one feature column must be selected.")

    excluded = [c for c in all_columns if c not in ordered and c != target]
    return ordered, excluded


class Preprocessor:
    """Fit/transform style missing-value handling with a fixed target/features view."""

    def __init__(self, dataframe, target, features, strategies=None):
        self.original_columns = list(dataframe.columns)
        self.target = target
        self.features, self.excluded = validate_selection(
            self.original_columns, target, features
        )
        self.strategies = dict(strategies or {})
        self._validate_strategies_defined()

        self._fill_values = {}
        self._is_fitted = False

    # -- validation -----------------------------------------------------------
    def _validate_strategies_defined(self):
        in_play = list(self.features) + [self.target]
        for col in in_play:
            strat = self.strategies.get(col, "")
            if strat == "" or strat is None:
                continue  # no explicit strategy for this column
            if strat not in _VALID_STRATEGIES:
                raise PreprocessingError(
                    f"Unknown missing-value strategy '{strat}' for column '{col}'."
                )

    def _validate_strategy_types(self, df):
        """Mean/median require numeric columns; catch it against the fitted frame."""
        for col in list(self.features) + [self.target]:
            strat = self.strategies.get(col)
            if strat in (MissingStrategy.MEAN, MissingStrategy.MEDIAN):
                if not is_numeric_column(df, col):
                    raise PreprocessingError(
                        f"Strategy '{strat}' requires a numeric column, "
                        f"but '{col}' is '{df[col].dtype}'."
                    )

    # -- fitting --------------------------------------------------------------
    def fit(self, train_df):
        """Compute imputation statistics from ``train_df`` only (no leakage)."""
        train_df = train_df[self.original_columns]
        self._validate_strategy_types(train_df)

        self._fill_values = {}
        for col in list(self.features) + [self.target]:
            strat = self.strategies.get(col)
            if strat not in _IMPUTE_STRATEGIES:
                continue
            series = train_df[col]
            if series.isna().all():
                raise PreprocessingError(
                    f"Column '{col}' is completely missing; it cannot be imputed "
                    f"with '{strat}'. Use row deletion or drop the column."
                )
            if strat == MissingStrategy.MEAN:
                self._fill_values[col] = float(series.mean())
            elif strat == MissingStrategy.MEDIAN:
                self._fill_values[col] = series.median()
            elif strat == MissingStrategy.MODE:
                modes = series.mode(dropna=True)
                if len(modes) == 0:
                    raise PreprocessingError(
                        f"Column '{col}' has no mode to impute (all values missing)."
                    )
                self._fill_values[col] = modes.iloc[0]

        self._is_fitted = True
        return self

    # -- transforming ---------------------------------------------------------
    def transform(self, df):
        """Return ``(X, y)`` after imputation/row-deletion, without mutating ``df``."""
        if not self._is_fitted:
            raise PreprocessingError("Preprocessor must be fitted before transform().")

        work = df[self.original_columns].copy()  # never touch the caller's dataframe

        # Row deletion: drop rows missing in ANY delete-designated column.
        delete_cols = [
            c for c in list(self.features) + [self.target]
            if self.strategies.get(c) == MissingStrategy.DELETE
        ]
        if delete_cols:
            mask = work[delete_cols].isna().any(axis=1)
            work = work[~mask]

        # Imputation using fitted statistics.
        for col, value in self._fill_values.items():
            if col in work.columns:
                work[col] = work[col].fillna(value)

        if work.shape[0] == 0:
            raise PreprocessingError(
                "Preprocessing removed all rows (missing-value deletion left an empty dataset)."
            )

        y = work[self.target]
        if y.isna().any():
            raise PreprocessingError(
                f"Target column '{self.target}' still contains missing values after "
                f"preprocessing; choose an imputation strategy or row deletion for it."
            )

        X = work[self.features].copy()
        y = y.copy()
        return X, y

    def fit_transform(self, train_df):
        return self.fit(train_df).transform(train_df)

    # -- accessors ------------------------------------------------------------
    def to_config_dict(self):
        return {
            "target_column": self.target,
            "feature_columns": self.features,
            "excluded_columns": self.excluded,
            "missing_strategies": self.strategies,
        }
