"""Errors raised while building the feature matrix and target vector (issue #8)."""


class PreprocessingError(Exception):
    """Raised for invalid target/feature selections or missing-value strategies."""
