"""Errors raised while validating or managing datasets (SAD section 4.4, MLE-F-063)."""


class DatasetRejected(Exception):
    """The upload failed a rule; ``str(exc)`` names the rule and what to change."""


class DatasetInUseError(Exception):
    """The dataset cannot be deleted because it is referenced by existing training runs."""


class DatasetAdminError(Exception):
    """Administrative action failed validation or authorization."""
