# WebUI (Django): issues #18 and #19

#18: upload form, target/feature selection and model selection, with the five-stage
workflow indicator (dataset, pipeline, model, run, results) on every page.

#19: start a run, show its state (Queued, Running, Completed, Failed), refresh it every
3 seconds, show elapsed time, the failure reason, and the metrics tables. The page works
without JavaScript too (it falls back to a 5-second page refresh).

## Run

    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements-webui.txt
    python manage.py migrate
    python manage.py createsuperuser        # temporary sign-in until AccountsApp is merged
    python manage.py runserver              # http://127.0.0.1:8000/
    python manage.py test                   # 69 tests

## Stand-ins to replace when the owning component is merged

| Stand-in file | Replaces | Keep this shape |
|---|---|---|
| `webui/standins/datasets.py` `validate_csv(uploaded)` | DatasetsApp (MLE-F-010..012) | returns `{rows, column_count, columns: [{name, dtype, missing_count, missing_pct}]}` or raises `DatasetRejected(message)` |
| `webui/standins/catalogue.py` `ALGORITHMS` | ModelsApp (MLE-F-030, F-031) | `(key, label, task)` |
| `webui/standins/runs.py` `start()`, `get_status()` | RunsApp and TrainingWorker (SAD interfaces 1 and 2), EvaluationApp metrics (#13) | `start(owner, dataset, run_config)` returns a job key; `get_status` returns `{job_key, state, started_at, elapsed_s, error}`; results use `accuracy, precision, recall, f1_score, confusion_matrix` or `mae, mse, rmse, r2` |
| `webui/models.py` `Run` | RunsApp's TrainingJob | state, error, result, run_config |
| `config/urls.py` login and logout | AccountsApp (MLE-F-001..003) | a signed-in `request.user` |

The chosen target, feature columns, excluded columns and algorithm are held in the
session until "Start run" turns them into the `run_config` of SAD 4.3. The pipeline
keys (`imputation`, `encoding`, `scaling`) stay empty until the pipeline settings exist.

The stand-in worker does not train the chosen algorithm. It scores a trivial baseline
(most frequent class, or the training mean) on a held-out split, and the results page
says so. Delete `webui/standins/runs.py` and point `views.py` at RunsApp to swap it out.
The delays are `STANDIN_QUEUE_SECONDS` and `STANDIN_RUN_SECONDS` in `config/settings.py`.
