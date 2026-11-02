import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django import forms

from webui.forms import UploadForm, PipelineForm, ModelForm, error_summary
from webui.standins.datasets import DatasetRejected


def test_upload_form_accepts_valid_csv(monkeypatch):
    expected_profile = {
        "rows": 25,
        "column_count": 2,
        "columns": [
            {"name": "age", "dtype": "integer", "missing_count": 0, "missing_pct": 0},
            {"name": "target", "dtype": "integer", "missing_count": 0, "missing_pct": 0},
        ],
    }

    monkeypatch.setattr(
        "webui.forms.validate_csv",
        lambda uploaded: expected_profile,
    )

    uploaded = SimpleUploadedFile(
        "data.csv",
        b"age,target\n20,1\n",
        content_type="text/csv",
    )

    form = UploadForm(files={"file": uploaded})

    assert form.is_valid()
    assert form.profile == expected_profile


def test_upload_form_rejects_invalid_csv(monkeypatch):
    def reject_file(uploaded):
        raise DatasetRejected("Invalid CSV file.")

    monkeypatch.setattr("webui.forms.validate_csv", reject_file)

    uploaded = SimpleUploadedFile(
        "bad.csv",
        b"invalid data",
        content_type="text/csv",
    )

    form = UploadForm(files={"file": uploaded})

    assert not form.is_valid()
    assert "Invalid CSV file." in str(form.errors)


def test_upload_form_requires_file():
    form = UploadForm(data={})

    assert not form.is_valid()
    assert "file" in form.errors


def test_pipeline_form_accepts_target_and_features():
    form = PipelineForm(
        ["age", "salary", "city"],
        data={
            "target": "salary",
            "role_0": "feature",
            "role_1": "excluded",
            "role_2": "feature",
        },
    )

    assert form.is_valid()
    assert form.cleaned_data["feature_columns"] == ["age", "city"]
    assert form.cleaned_data["excluded_columns"] == []


def test_pipeline_form_rejects_invalid_target():
    form = PipelineForm(
        ["age", "salary"],
        data={
            "target": "unknown",
            "role_0": "feature",
            "role_1": "feature",
        },
    )

    assert not form.is_valid()
    assert "target" in form.errors


def test_pipeline_form_requires_at_least_one_feature():
    form = PipelineForm(
        ["age", "salary"],
        data={
            "target": "salary",
            "role_0": "excluded",
            "role_1": "feature",
        },
    )

    assert not form.is_valid()
    assert any(
        "at least one column" in error.lower()
        for error in form.non_field_errors()
    )


def test_pipeline_form_role_rows():
    form = PipelineForm(["age", "salary"])

    rows = form.role_rows()

    assert len(rows) == 2
    assert rows[0]["name"] == "age"
    assert rows[1]["name"] == "salary"
    assert rows[0]["field"] == form["role_0"]


def test_model_form_contains_classification_and_regression_choices():
    form = ModelForm()

    choices = form.fields["algorithm"].choices
    labels = [label for label, options in choices if isinstance(options, list)]

    assert "Classification" in labels
    assert "Regression" in labels


def test_model_form_rejects_unknown_algorithm():
    form = ModelForm(data={"algorithm": "unknown_model"})

    assert not form.is_valid()
    assert "algorithm" in form.errors


def test_error_summary_uses_target_anchor_for_general_error():
    form = PipelineForm(
        ["age", "salary"],
        data={
            "target": "salary",
            "role_0": "excluded",
            "role_1": "feature",
        },
    )

    assert not form.is_valid()

    summary = error_summary(form)

    assert summary
    assert summary[0][0] == form["target"].auto_id


def test_error_summary_uses_radio_anchor_for_role_errors():
    form = PipelineForm(
        ["age", "salary"],
        data={
            "target": "salary",
            "role_0": "invalid",
            "role_1": "feature",
        },
    )

    assert not form.is_valid()

    summary = error_summary(form)

    assert any(
        anchor == "id_role_0_0"
        for anchor, message in summary
    )


def test_model_form_requires_algorithm():
    form = ModelForm(data={})

    assert not form.is_valid()
    assert "algorithm" in form.errors