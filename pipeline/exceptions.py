"""Exception classes for the Data Preprocessing Pipeline (MLE-F-020..023)."""


class PipelineError(Exception):
    """Base exception for all pipeline errors."""


class InvalidConfigError(PipelineError):
    """Configuration structure or values are invalid."""


class InvalidTargetError(PipelineError):
    """Target column is missing, invalid, or conflicts with feature columns."""


class InvalidFeatureError(PipelineError):
    """Feature columns are empty, missing, or invalid."""


class InvalidImputationError(PipelineError):
    """Imputation strategy is unrecognized or incompatible with column dtype."""


class InvalidEncodingError(PipelineError):
    """Categorical encoding choice is unrecognized or incompatible."""


class InvalidScalingError(PipelineError):
    """Numeric scaling choice is unrecognized or incompatible."""


class InvalidSplitRatioError(PipelineError):
    """Split ratio is outside the allowed [0.5, 0.9] range."""


class InsufficientRowsError(PipelineError):
    """Dataset has too few rows to split or train after row deletion."""


class DataLeakageError(PipelineError):
    """Raised when data leakage between train and test sets is detected."""


class CorruptedDatasetError(PipelineError):
    """Dataset file is missing, empty, or unparseable."""
