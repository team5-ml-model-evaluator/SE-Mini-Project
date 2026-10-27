from django import forms

from .standins.catalogue import ALGORITHMS
from .standins.datasets import DatasetRejected, validate_csv

ROLE_CHOICES = [("feature", "Feature"), ("excluded", "Excluded")]


class UploadForm(forms.Form):
    file = forms.FileField(
        label="CSV file",
        help_text="Comma-separated values, UTF-8, a header row, at least 20 rows and 2 columns, up to 50 MB.",
        error_messages={"required": "Choose a CSV file to upload."},
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        try:
            self.profile = validate_csv(uploaded)
        except DatasetRejected as exc:
            raise forms.ValidationError(str(exc))
        return uploaded


class PipelineForm(forms.Form):
    """Pick one target column and mark every other column as a feature or excluded (MLE-F-020)."""

    target = forms.ChoiceField(
        label="Column to predict (target)",
        error_messages={
            "required": "Choose the column to predict.",
            "invalid_choice": "Choose the column to predict from the list.",
        },
    )

    def __init__(self, column_names, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.column_names = column_names
        self.fields["target"].choices = [("", "Choose a column")] + [(n, n) for n in column_names]
        self.fields["target"].widget.attrs["class"] = "form-select"
        for index in range(len(column_names)):
            self.fields[f"role_{index}"] = forms.ChoiceField(
                label=column_names[index],
                choices=ROLE_CHOICES,
                initial="feature",
                widget=forms.RadioSelect(attrs={"class": "btn-check"}),
                error_messages={"required": f"Mark “{column_names[index]}” as a feature or excluded."},
            )

    def role_rows(self):
        """One row per column for the template: its name and its bound radio field."""
        return [{"name": name, "field": self[f"role_{i}"]} for i, name in enumerate(self.column_names)]

    def clean(self):
        data = super().clean()
        target = data.get("target")
        if not target:
            return data
        features = [
            name
            for i, name in enumerate(self.column_names)
            if name != target and data.get(f"role_{i}") == "feature"
        ]
        if not features:
            raise forms.ValidationError(
                "Mark at least one column other than the target as a feature, "
                "or the model has nothing to learn from."
            )
        data["feature_columns"] = features
        data["excluded_columns"] = [n for n in self.column_names if n != target and n not in features]
        return data


class ModelForm(forms.Form):
    algorithm = forms.ChoiceField(
        label="Algorithm",
        error_messages={
            "required": "Choose an algorithm.",
            "invalid_choice": "Choose an algorithm from the list.",
        },
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        grouped = [
            (task.capitalize(), [(a.key, a.label) for a in ALGORITHMS if a.task == task])
            for task in ("classification", "regression")
        ]
        self.fields["algorithm"].choices = [("", "Choose an algorithm")] + grouped


def error_summary(form):
    """List of (anchor id, message) for the error summary shown above a form."""
    items = []
    for name, errors in form.errors.items():
        if name == "__all__":
            anchor = form["target"].auto_id if "target" in form.fields else None
        elif name.startswith("role_"):
            anchor = f"{form[name].auto_id}_0"  # first radio of the group
        else:
            anchor = form[name].auto_id
        items.extend((anchor, message) for message in errors)
    return items
