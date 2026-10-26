"""Errors raised while validating an uploaded dataset (SAD section 4.4)."""


class DatasetRejected(Exception):
    """The upload failed a rule; ``str(exc)`` names the rule and what to change."""
