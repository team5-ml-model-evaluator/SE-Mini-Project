"""Core Preprocessing Engine for the Data Pipeline (MLE-F-020..023).

Responsibilities:
- MLE-F-020: Target and feature selection; excluded columns absent from output (TC-PP-01).
- MLE-F-021: Imputation strategies: mean, median, mode, row deletion (TC-PP-02).
- MLE-F-022: Categorical encoding (one-hot, label) and numeric scaling (standard, min-max) (TC-PP-03).
- MLE-F-023: Seeded train/test split with training ratio between 50% and 90% (TC-PP-04).
- Anti-leakage: All transformations (imputation, encoding, scaling) fit ONLY on training data.
- Safe handling of unseen categories and missing values.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, OrdinalEncoder, StandardScaler

from .exceptions import (
    CorruptedDatasetError,
    DataLeakageError,
    InsufficientRowsError,
    InvalidConfigError,
    InvalidEncodingError,
    InvalidFeatureError,
    InvalidImputationError,
    InvalidScalingError,
    InvalidSplitRatioError,
    InvalidTargetError,
)

MIN_SPLIT_RATIO = 0.5
MAX_SPLIT_RATIO = 0.9
VALID_IMPUTATION_STRATEGIES = {"mean", "median", "mode", "most_frequent", "row_deletion", "row deletion", "drop", "none"}
VALID_ENCODINGS = {"one_hot", "onehot", "one-hot", "label", "label_encoding", "ordinal", "none", None}
VALID_SCALINGS = {"standard", "standardscaler", "standardisation", "standardization", "minmax", "min_max", "minmaxscaler", "none", None}


@dataclass
class PreprocessedData:
    """Container holding preprocessed train and test partitions and metadata."""

    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: list[str]
    target_name: str
    train_indices: list[int]
    test_indices: list[int]
    random_seed: int
    split_ratio: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item) from None

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def keys(self):
        return [
            "X_train",
            "X_test",
            "y_train",
            "y_test",
            "feature_names",
            "target_name",
            "train_indices",
            "test_indices",
            "random_seed",
            "split_ratio",
            "metadata",
        ]

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]


def validate_pipeline_config(config: Mapping[str, Any], available_columns: list[str] | None = None) -> dict[str, Any]:
    """Validate pipeline configuration structure and values; return normalized config dict.

    Raises InvalidConfigError, InvalidTargetError, InvalidFeatureError,
    InvalidSplitRatioError, InvalidImputationError, InvalidEncodingError, or InvalidScalingError.
    """
    if not isinstance(config, Mapping):
        raise InvalidConfigError(f"Configuration must be a dictionary or mapping, got {type(config).__name__}.")

    target_column = config.get("target_column")
    if not target_column or not isinstance(target_column, str) or not target_column.strip():
        raise InvalidTargetError("A non-empty string target_column must be specified.")
    target_column = target_column.strip()

    feature_columns = config.get("feature_columns")
    if feature_columns is None or not isinstance(feature_columns, (list, tuple)):
        raise InvalidFeatureError("feature_columns must be a non-empty list of column names.")
    feature_columns = [str(c).strip() for c in feature_columns if str(c).strip()]
    if not feature_columns:
        raise InvalidFeatureError("At least one feature column must be selected.")

    if target_column in feature_columns:
        raise InvalidTargetError(f"Target column “{target_column}” cannot also be included in feature_columns.")

    excluded_columns = [str(c).strip() for c in config.get("excluded_columns", [])]

    if available_columns is not None:
        col_set = set(available_columns)
        if target_column not in col_set:
            raise InvalidTargetError(
                f"Target column “{target_column}” does not exist in the dataset. Available columns: {available_columns}."
            )
        missing_features = [f for f in feature_columns if f not in col_set]
        if missing_features:
            raise InvalidFeatureError(
                f"Feature columns {missing_features} do not exist in the dataset. Available columns: {available_columns}."
            )

    split_ratio = config.get("split_ratio", 0.8)
    try:
        split_ratio = float(split_ratio)
    except (ValueError, TypeError):
        raise InvalidSplitRatioError(f"split_ratio must be a numeric value, got {split_ratio!r}.") from None

    if not (MIN_SPLIT_RATIO <= split_ratio <= MAX_SPLIT_RATIO):
        raise InvalidSplitRatioError(
            f"Split ratio must be between {MIN_SPLIT_RATIO} (50:50) and {MAX_SPLIT_RATIO} (90:10), got {split_ratio}."
        )

    random_seed = config.get("random_seed", 42)
    try:
        random_seed = int(random_seed)
    except (ValueError, TypeError):
        raise InvalidConfigError(f"random_seed must be an integer, got {random_seed!r}.") from None

    # Normalise encoding
    encoding = config.get("encoding", "none")
    if encoding is not None:
        encoding_str = str(encoding).lower().strip()
        if encoding_str in {"one_hot", "onehot", "one-hot"}:
            norm_encoding = "one_hot"
        elif encoding_str in {"label", "label_encoding", "ordinal"}:
            norm_encoding = "label"
        elif encoding_str in {"none", ""}:
            norm_encoding = "none"
        else:
            raise InvalidEncodingError(
                f"Unknown encoding “{encoding}”. Supported encodings: 'one_hot', 'label', 'none'."
            )
    else:
        norm_encoding = "none"

    # Normalise scaling
    scaling = config.get("scaling", "none")
    if scaling is not None:
        scaling_str = str(scaling).lower().strip()
        if scaling_str in {"standard", "standardscaler", "standardisation", "standardization"}:
            norm_scaling = "standard"
        elif scaling_str in {"minmax", "min_max", "minmaxscaler"}:
            norm_scaling = "minmax"
        elif scaling_str in {"none", ""}:
            norm_scaling = "none"
        else:
            raise InvalidScalingError(
                f"Unknown scaling “{scaling}”. Supported scalings: 'standard', 'minmax', 'none'."
            )
    else:
        norm_scaling = "none"

    # Normalise imputation
    raw_imputation = config.get("imputation", {})
    imputation_map: dict[str, str] = {}
    if isinstance(raw_imputation, str):
        strat = raw_imputation.lower().strip()
        if strat not in VALID_IMPUTATION_STRATEGIES:
            raise InvalidImputationError(f"Unknown imputation strategy “{raw_imputation}”.")
        imputation_map["__default__"] = strat
    elif isinstance(raw_imputation, Mapping):
        for col, strat in raw_imputation.items():
            strat_str = str(strat).lower().strip()
            if strat_str not in VALID_IMPUTATION_STRATEGIES:
                raise InvalidImputationError(f"Unknown imputation strategy “{strat}” for column “{col}”.")
            imputation_map[col] = strat_str
    elif raw_imputation is None:
        imputation_map = {}
    else:
        raise InvalidImputationError("imputation must be a dictionary or strategy string.")

    return {
        "dataset_id": config.get("dataset_id"),
        "target_column": target_column,
        "feature_columns": feature_columns,
        "excluded_columns": excluded_columns,
        "imputation": imputation_map,
        "encoding": norm_encoding,
        "scaling": norm_scaling,
        "split_ratio": split_ratio,
        "random_seed": random_seed,
    }


def _load_dataframe(source: Any) -> pd.DataFrame:
    """Load a pandas DataFrame from a DataFrame, Django Dataset model, filepath, or file buffer."""
    if isinstance(source, pd.DataFrame):
        return source.copy()

    # Django Dataset model instance
    if hasattr(source, "file") and hasattr(source.file, "path"):
        file_path = source.file.path
        if not os.path.exists(file_path):
            raise CorruptedDatasetError(f"Dataset file is missing from storage: {file_path}")
        try:
            return pd.read_csv(file_path)
        except Exception as exc:
            raise CorruptedDatasetError(f"Failed to read dataset file: {exc}") from exc

    if hasattr(source, "file") and hasattr(source.file, "open"):
        try:
            with source.file.open("rb") as handle:
                content = handle.read()
            return pd.read_csv(io.BytesIO(content))
        except Exception as exc:
            raise CorruptedDatasetError(f"Failed to read dataset file: {exc}") from exc

    if isinstance(source, (str, Path)):
        if not os.path.exists(source):
            raise CorruptedDatasetError(f"File not found: {source}")
        try:
            return pd.read_csv(source)
        except Exception as exc:
            raise CorruptedDatasetError(f"Failed to parse CSV file “{source}”: {exc}") from exc

    if hasattr(source, "read"):
        try:
            return pd.read_csv(source)
        except Exception as exc:
            raise CorruptedDatasetError(f"Failed to parse CSV data: {exc}") from exc

    raise CorruptedDatasetError(f"Unsupported data source type: {type(source).__name__}")


class Preprocessor:
    """Stateful preprocessing pipeline that enforces training-only fitting (zero leakage)."""

    def __init__(self, config: Mapping[str, Any]):
        self.raw_config = dict(config)
        self.config = validate_pipeline_config(config)
        self.imputers: dict[str, Any] = {}
        self.encoder: Any = None
        self.scaler: Any = None
        self.categorical_columns: list[str] = []
        self.numeric_columns: list[str] = []
        self.feature_names: list[str] = []

    def fit_transform(self, df: pd.DataFrame) -> PreprocessedData:
        """Fit transformations ONLY on training split and transform train and test."""
        # Validate columns against loaded dataframe
        validate_pipeline_config(self.config, available_columns=list(df.columns))

        target_col = self.config["target_column"]
        feature_cols = self.config["feature_columns"]
        imputation_map = self.config["imputation"]
        encoding_choice = self.config["encoding"]
        scaling_choice = self.config["scaling"]
        split_ratio = self.config["split_ratio"]
        random_seed = self.config["random_seed"]

        # Drop rows where target is NaN (cannot train or evaluate without target)
        working_df = df.dropna(subset=[target_col]).copy()
        if len(working_df) < 2:
            raise InsufficientRowsError(
                f"Dataset has only {len(working_df)} row(s) with valid target values. At least 2 are required."
            )

        # Handle row_deletion strategy if specified for any feature columns
        row_del_cols = [
            c for c in feature_cols
            if imputation_map.get(c) in {"row_deletion", "row deletion", "drop"}
            or (c not in imputation_map and imputation_map.get("__default__") in {"row_deletion", "row deletion", "drop"})
        ]
        if row_del_cols:
            working_df = working_df.dropna(subset=row_del_cols).copy()
            if len(working_df) < 2:
                raise InsufficientRowsError(
                    f"Insufficient rows remaining after row deletion ({len(working_df)} rows). At least 2 are needed."
                )

        # Ensure train/test split has at least 1 sample in each
        test_size = 1.0 - split_ratio
        expected_test_rows = int(round(len(working_df) * test_size))
        expected_train_rows = len(working_df) - expected_test_rows
        if expected_test_rows < 1 or expected_train_rows < 1:
            raise InsufficientRowsError(
                f"Dataset with {len(working_df)} rows cannot be split with split_ratio={split_ratio} "
                "without leaving an empty train or test partition."
            )

        # 1. SPLIT BEFORE ANY TRANSFORMATION TO PREVENT DATA LEAKAGE
        X_raw = working_df[feature_cols].copy()
        y_raw = working_df[target_col].copy()

        train_indices, test_indices = train_test_split(
            working_df.index.tolist(),
            train_size=split_ratio,
            random_state=random_seed,
            shuffle=True,
        )

        X_train = X_raw.loc[train_indices].copy()
        X_test = X_raw.loc[test_indices].copy()
        y_train = y_raw.loc[train_indices].to_numpy()
        y_test = y_raw.loc[test_indices].to_numpy()

        # 2. IMPUTATION (Fitted on X_train ONLY)
        for col in feature_cols:
            strategy = imputation_map.get(col, imputation_map.get("__default__"))
            if not strategy or strategy in {"none", "row_deletion", "row deletion", "drop"}:
                continue

            col_train = X_train[col]
            is_numeric = pd.api.types.is_numeric_dtype(col_train)

            if strategy in {"mean", "median"}:
                if not is_numeric:
                    raise InvalidImputationError(
                        f"Cannot apply '{strategy}' imputation to non-numeric column “{col}” (dtype {col_train.dtype})."
                    )
                non_nulls = col_train.dropna()
                if non_nulls.empty:
                    raise InvalidImputationError(
                        f"Column “{col}” contains no non-null values in the training set to compute {strategy}."
                    )
                fill_value = float(non_nulls.mean() if strategy == "mean" else non_nulls.median())
                self.imputers[col] = {"strategy": strategy, "fill_value": fill_value}
                X_train[col] = X_train[col].fillna(fill_value)
                X_test[col] = X_test[col].fillna(fill_value)

            elif strategy in {"mode", "most_frequent"}:
                non_nulls = col_train.dropna()
                if non_nulls.empty:
                    raise InvalidImputationError(
                        f"Column “{col}” contains no non-null values in the training set to compute mode."
                    )
                modes = non_nulls.mode()
                # Deterministic tie-breaking
                fill_value = sorted(modes.tolist())[0] if len(modes) > 1 else modes.iloc[0]
                self.imputers[col] = {"strategy": "mode", "fill_value": fill_value}
                X_train[col] = X_train[col].fillna(fill_value)
                X_test[col] = X_test[col].fillna(fill_value)

        # 3. IDENTIFY NUMERIC VS CATEGORICAL FEATURES
        self.numeric_columns = [c for c in feature_cols if pd.api.types.is_numeric_dtype(X_train[c])]
        self.categorical_columns = [c for c in feature_cols if c not in self.numeric_columns]

        # 4. CATEGORICAL ENCODING (Fitted on X_train ONLY)
        cat_train_encoded = None
        cat_test_encoded = None
        cat_feature_names: list[str] = []

        if self.categorical_columns:
            # Convert all to strings, treating missing as 'missing' for safe transformation
            X_train_cat = X_train[self.categorical_columns].astype(str)
            X_test_cat = X_test[self.categorical_columns].astype(str)

            if encoding_choice == "one_hot":
                self.encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
                cat_train_encoded = self.encoder.fit_transform(X_train_cat)
                cat_test_encoded = self.encoder.transform(X_test_cat)
                cat_feature_names = list(self.encoder.get_feature_names_out(self.categorical_columns))
            elif encoding_choice == "label":
                self.encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
                cat_train_encoded = self.encoder.fit_transform(X_train_cat)
                cat_test_encoded = self.encoder.transform(X_test_cat)
                cat_feature_names = list(self.categorical_columns)
            else:
                # "none" encoding: categorical columns cannot be scaled or converted to float matrix directly
                # If scaling or numpy array is requested, warn or convert as object array
                cat_train_encoded = X_train_cat.to_numpy()
                cat_test_encoded = X_test_cat.to_numpy()
                cat_feature_names = list(self.categorical_columns)

        # 5. NUMERIC SCALING (Fitted on X_train ONLY)
        num_train_scaled = None
        num_test_scaled = None
        num_feature_names = list(self.numeric_columns)

        if self.numeric_columns:
            # Check for remaining NaNs in numeric columns before scaling
            if X_train[self.numeric_columns].isna().any().any():
                # Fill remaining with 0 or raise if unhandled
                X_train[self.numeric_columns] = X_train[self.numeric_columns].fillna(0.0)
                X_test[self.numeric_columns] = X_test[self.numeric_columns].fillna(0.0)

            X_train_num = X_train[self.numeric_columns].astype(float)
            X_test_num = X_test[self.numeric_columns].astype(float)

            if scaling_choice == "standard":
                self.scaler = StandardScaler()
                num_train_scaled = self.scaler.fit_transform(X_train_num)
                num_test_scaled = self.scaler.transform(X_test_num)
            elif scaling_choice == "minmax":
                self.scaler = MinMaxScaler()
                num_train_scaled = self.scaler.fit_transform(X_train_num)
                num_test_scaled = self.scaler.transform(X_test_num)
            else:
                num_train_scaled = X_train_num.to_numpy()
                num_test_scaled = X_test_num.to_numpy()

        # 6. ASSEMBLE FINAL FEATURE MATRICES (MLE-F-020: excluded columns absent)
        parts_train = []
        parts_test = []
        final_feature_names = []

        if num_train_scaled is not None and len(num_feature_names) > 0:
            parts_train.append(num_train_scaled)
            parts_test.append(num_test_scaled)
            final_feature_names.extend(num_feature_names)

        if cat_train_encoded is not None and len(cat_feature_names) > 0:
            parts_train.append(cat_train_encoded)
            parts_test.append(cat_test_encoded)
            final_feature_names.extend(cat_feature_names)

        if parts_train:
            final_X_train = np.hstack(parts_train)
            final_X_test = np.hstack(parts_test)
        else:
            final_X_train = np.empty((len(train_indices), 0))
            final_X_test = np.empty((len(test_indices), 0))

        self.feature_names = final_feature_names

        # TC-PP-01 check: verify excluded columns are nowhere in feature_names or matrix
        for excluded in self.config.get("excluded_columns", []):
            if excluded in self.feature_names:
                raise DataLeakageError(f"Excluded column “{excluded}” leaked into preprocessed feature names!")

        metadata = {
            "imputers": self.imputers,
            "categorical_columns": self.categorical_columns,
            "numeric_columns": self.numeric_columns,
            "encoding": encoding_choice,
            "scaling": scaling_choice,
            "raw_shape": df.shape,
            "train_shape": final_X_train.shape,
            "test_shape": final_X_test.shape,
        }

        return PreprocessedData(
            X_train=final_X_train,
            X_test=final_X_test,
            y_train=y_train,
            y_test=y_test,
            feature_names=final_feature_names,
            target_name=target_col,
            train_indices=train_indices,
            test_indices=test_indices,
            random_seed=random_seed,
            split_ratio=split_ratio,
            metadata=metadata,
        )


def prepare_data(dataset_or_df_or_path: Any, config: Mapping[str, Any]) -> PreprocessedData:
    """Preprocess a dataset according to config.

    Accepts DataFrame, path string, file-like object, or Django Dataset instance.
    Fulfills MLE-F-020, MLE-F-021, MLE-F-022, and MLE-F-023.
    """
    df = _load_dataframe(dataset_or_df_or_path)
    preprocessor = Preprocessor(config)
    return preprocessor.fit_transform(df)
