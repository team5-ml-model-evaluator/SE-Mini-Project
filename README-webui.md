# WebUI (Django): issue #18, core workflow forms

Upload form, target/feature selection and model selection, with the five-stage
workflow indicator (dataset, pipeline, model, run, results) on every page.

## Run

    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements-webui.txt
    python manage.py migrate
    python manage.py createsuperuser        # temporary sign-in until AccountsApp is merged
    python manage.py runserver              # http://127.0.0.1:8000/
    python manage.py test                   # 34 tests

## Stand-ins to replace when the owning component is merged

| Stand-in file | Replaces | Keep this shape |
|---|---|---|
| `webui/standins/datasets.py` `validate_csv(uploaded)` | DatasetsApp (MLE-F-010..012) | returns `{rows, column_count, columns: [{name, dtype, missing_count, missing_pct}]}` or raises `DatasetRejected(message)` |
| `webui/standins/catalogue.py` `ALGORITHMS` | ModelsApp (MLE-F-030, F-031) | `(key, label, task)` |
| `config/urls.py` login and logout | AccountsApp (MLE-F-001..003) | a signed-in `request.user` |

The chosen target, feature columns, excluded columns and algorithm are held in the
session until the run step (issue #19) turns them into the `run_config` of SAD 4.3.
