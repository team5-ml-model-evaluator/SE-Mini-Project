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

## Multi-run comparison (#20)

Open a dataset or a completed run and choose **Compare completed runs**. Select
two or more completed runs with the same dataset, target column and task type.
Different algorithms, feature selections and preprocessing configurations are
allowed. Only the signed-in user's completed runs for that dataset are listed.

The comparison shows stored metrics side by side: classification metrics as
percentages to two decimal places, and regression metrics as numbers to two
decimal places, without changing stored precision. Classification comparisons include each run's labelled confusion
matrix. The table scrolls horizontally for additional runs and can be reached
with the keyboard. Invalid selections or incomplete evaluation data show an
explanatory message. Placeholder baseline results are explicitly identified.

For more than 20 classes, comparison shows an explicitly labelled 20 × 20
matrix preview. **Browse full matrix** opens the run's paginated matrix; separate
actual-class and predicted-class controls make every stored cell accessible.
Run selection and status polling do not load the stored result matrices.

The route is `/datasets/<dataset-id>/compare/`. Comparison data is prepared in
`webui/comparison.py` so a future report/CSV export can reuse the same values.
No database migration or additional package is needed.

Run the focused tests with `python manage.py test webui.test_comparison`.

Model selection also checks likely numeric-amount targets before classification
training: a numeric target with more than 20 distinct values and more than half
its non-missing rows distinct is rejected with guidance to choose regression or
a categorical target. This heuristic allows numeric category codes such as 0/1.
The start-run endpoint repeats the check for previously saved drafts.
Run its tests with `python manage.py test webui.test_target_validation`.

## Evaluation reports and comparison CSV (#21)

Completed run pages offer **Download PDF report** and **Download HTML report**.
The default client report uses a compact scorecard: model, prediction target,
dataset and evaluation sizes, input fields, formatted performance metrics, and a
small prediction-breakdown table when there are six or fewer classes. Internal
IDs, timestamps and training configuration are omitted from this client summary.

Expand **Technical report (optional)** for full PDF/HTML downloads, including
column profiles, excluded columns, split/seed, requested and effective
preprocessing and hyperparameters, full stored metric precision, and complete
classification matrix counts. These downloads use `?details=1`; default links
remain client summaries. Both variants use the same authorization checks.
Technical field lists use readable names and show **None** when no fields are
excluded; absent historical configuration remains **Not recorded for this run**.

The comparison page offers **Download comparison CSV** for exactly the selected
runs in the displayed order. Each score column names the model and run key,
for example `Decision Tree (r-example)`. Classification metrics use two-decimal percentages;
regression metrics use two-decimal numeric values. Run pages use the same score
formatting. Class inventories and sparse
matrix counts follow the metric rows. Unlisted class pairs have count zero.

Reports and CSV require sign-in and server-side ownership checks. Unfinished or
invalid results cannot be exported. User-controlled CSV labels are protected
against spreadsheet formulas. The HTML file is self-contained and printable.
The PDF uses an embedded font; unsupported glyphs are preserved as explicit
Unicode escapes with an explanatory note rather than silently replaced.

New runs save their effective preprocessing and estimator hyperparameters in
`Run.result.execution`. Older runs label absent metadata **Not recorded for this
run**. They are not retroactively assigned current defaults. Excluded columns can
be derived from recorded features, and this derivation is labelled in the report.

Install with `pip install -r requirements-webui.txt`; ReportLab generates PDFs,
and pypdf validates PDF content in tests. No database migration is needed.
Run focused tests with `python manage.py test webui.test_reports`.
