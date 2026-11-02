from django import forms

from .exceptions import PreprocessingError
from .models import MissingStrategy
from .service import validate_selection


class PreprocessingForm(forms.Form):
    """Dynamic form: one target, N feature checkboxes, per-column missing strategy.

    ``columns`` is the ordered list of the dataset's column names. Strategy
    selects are keyed by column position (``strategy_<i>``) so that column names
    with spaces or punctuation never become HTML field names.
    """

    STRATEGY_CHOICES = [("", "(leave as-is)")] + list(MissingStrategy.choices)

    def __init__(self, *args, columns=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.columns = list(columns or [])

        self.fields["target"] = forms.ChoiceField(
            label="Target column",
            choices=[("", "— select target —")] + [(c, c) for c in self.columns],
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        self.fields["features"] = forms.MultipleChoiceField(
            label="Feature columns",
            choices=[(c, c) for c in self.columns],
            widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
            help_text="Select the columns to keep as features. The target cannot be a feature.",
        )
        for i, col in enumerate(self.columns):
            self.fields[f"strategy_{i}"] = forms.ChoiceField(
                label=col,
                required=False,
                choices=self.STRATEGY_CHOICES,
                widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
            )

    def clean(self):
        cleaned = super().clean()
        target = cleaned.get("target")
        features = cleaned.get("features")

        if not target:
            self.add_error("target", "A target column must be selected.")
            return cleaned
        if target not in self.columns:
            self.add_error("target", "Selected target column is not valid.")
            return cleaned

        try:
            ordered_features, excluded = validate_selection(self.columns, target, features or [])
        except PreprocessingError as exc:
            # A target that is also selected as a feature is a features error.
            field = "features" if "feature" in str(exc).lower() else "target"
            self.add_error(field, str(exc))
            return cleaned

        cleaned["_features"] = ordered_features
        cleaned["_excluded"] = excluded

        strategies = {}
        valid = {c.value for c in MissingStrategy}
        for i, col in enumerate(self.columns):
            strat = cleaned.get(f"strategy_{i}", "") or ""
            if strat in valid and (col == target or col in ordered_features):
                strategies[col] = strat
        cleaned["_strategies"] = strategies
        return cleaned
