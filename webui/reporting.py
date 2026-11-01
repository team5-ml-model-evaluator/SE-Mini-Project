"""Shared report content and safe download serialization for issue #21."""
import csv
import io
import json
from datetime import timezone as datetime_timezone
from pathlib import Path
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from .comparison import METRICS, describe_run, format_metric


NOT_RECORDED = "Not recorded for this run"
pdfmetrics.registerFont(TTFont("ReportSans", str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ReportSansBold", str(Path(reportlab.__file__).parent / "fonts" / "VeraBd.ttf")))


def _text(value):
    if value is None:
        return NOT_RECORDED
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _field_list(value):
    if isinstance(value, list):
        return ", ".join(str(name) for name in value) or "None"
    return _text(value)


def _timestamp(value):
    return value.astimezone(datetime_timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if value else NOT_RECORDED


def nonzero_matrix(result):
    """Lossless sparse form: every omitted class pair has count zero."""
    labels = result["labels"]
    return [(labels[i], labels[j], value) for i, row in enumerate(result["confusion_matrix"])
            for j, value in enumerate(row) if value]


def build_report(run, detailed=False):
    column = describe_run(run)
    dataset, config, result = run.dataset, run.run_config, run.result
    execution = result.get("execution") or {}
    if not isinstance(execution, dict):
        raise ValidationError("The saved report configuration is invalid.")
    preprocessing = execution.get("preprocessing") or {}
    parameters = execution.get("hyperparameters")
    if not isinstance(preprocessing, dict) or (parameters is not None and not isinstance(parameters, dict)):
        raise ValidationError("The saved report configuration is invalid.")
    requested = config.get("hyperparameters")
    if requested is not None and not isinstance(requested, dict):
        raise ValidationError("The saved report configuration is invalid.")
    features = config.get("feature_columns")
    excluded = config.get("excluded_columns")
    excluded_label = "Excluded columns"
    if excluded is None and isinstance(features, list):
        excluded = [name for name in dataset.column_names if name != column["target"] and name not in features]
        excluded_label = "Excluded columns (derived from recorded features)"
    sections = [
        {"title": "Run", "rows": [("Run key", run.job_key), ("Status", run.state),
            ("Created", _timestamp(run.created_at)), ("Started", _timestamp(run.started_at)),
            ("Finished", _timestamp(run.finished_at)), ("Elapsed seconds", _text(run.elapsed_s))]},
        {"title": "Dataset summary", "rows": [("File", dataset.original_name), ("Dataset ID", str(dataset.id)),
            ("Rows", str(dataset.rows)), ("Columns", str(dataset.column_count)),
            ("Uploaded", _timestamp(dataset.created_at))]},
        {"title": "Run configuration", "rows": [("Task", column["task"]), ("Target", column["target"]),
            ("Features", _field_list(features)), (excluded_label, _field_list(excluded)),
            ("Algorithm", column["algorithm"].label), ("Training split ratio", _text(config.get("split_ratio"))),
            ("Random seed", _text(config.get("random_seed"))), ("Test rows", _text(result.get("test_rows")))]},
        {"title": "Preprocessing", "rows": [
            (f"Requested {key}", _text(config.get(key))) for key in ("imputation", "encoding", "scaling")] + [
            (f"Effective {key}", _text(preprocessing.get(key))) for key in ("imputation", "encoding", "scaling")]},
        {"title": "Requested hyperparameters", "rows": [(str(key), _text(value))
            for key, value in (requested or {}).items()] or [("Settings", "Algorithm defaults requested" if requested == {} else NOT_RECORDED)]},
        {"title": "Effective hyperparameters", "rows": [(str(key), _text(value))
            for key, value in (parameters or {}).items()] or [("Settings", NOT_RECORDED)]},
    ]
    profile = [[_text(c.get(key)) for key in ("name", "dtype", "missing_count", "missing_pct")]
               for c in dataset.profile.get("columns", [])]
    metrics = [{"label": label, "raw": str(result[key]), "display": format_metric(column["task"], result[key])}
               for key, label in METRICS[column["task"]]]
    notes = {
        "Accuracy": "Correct prediction rate", "Precision": "Precision across classes (weighted)",
        "Recall": "Recall across classes (weighted)", "F1-score": "Precision / recall balance (weighted)",
        "MAE": "Average absolute error", "MSE": "Average squared error",
        "RMSE": "Error in target units", "R²": "Fit relative to predicting the mean",
    }
    for metric in metrics:
        metric["description"] = notes[metric["label"]]
    facts = [("Dataset", dataset.original_name), ("Prediction target", column["target"]),
             ("Dataset records", str(dataset.rows))]
    if result.get("test_rows") is not None:
        facts.append(("Records evaluated", str(result["test_rows"])))
    if isinstance(features, list):
        facts.append(("Input fields", str(len(features))))
    labels = result.get("labels", [])
    breakdown = []
    if column["task"] == "classification" and len(labels) <= 6:
        breakdown = [{"label": label, "values": row} for label, row in zip(labels, result["confusion_matrix"])]
    return {"run_key": run.job_key, "dataset_name": dataset.original_name, "task": column["task"],
            "detailed": detailed, "algorithm": column["algorithm"].label,
            "facts": facts, "features": features if isinstance(features, list) else None,
            "breakdown": breakdown,
            "sections": sections, "profile": profile, "metrics": metrics,
            "placeholder": bool(result.get("standin")),
            "labels": labels,
            "matrix_entries": nonzero_matrix(result) if detailed and column["task"] == "classification" else []}


def _csv_label(value):
    """Prevent user-controlled labels from becoming spreadsheet formulas."""
    value = str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def comparison_csv(comparison):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    columns = comparison["columns"]
    keys = [_csv_label(f"{column['algorithm'].label} ({column['run'].job_key})") for column in columns]
    writer.writerow(["Metric", *keys])
    for row in comparison["rows"]:
        writer.writerow([row["label"], *row["display_values"]])
    if comparison["task"] == "classification":
        writer.writerow([])
        writer.writerow(["Class labels (ordered)"])
        writer.writerow(["Run", "Class index", "Label"])
        for column in columns:
            for index, label in enumerate(column["run"].result["labels"]):
                writer.writerow([_csv_label(column["run"].job_key), index, _csv_label(label)])
        writer.writerow([])
        writer.writerow(["Confusion matrix: unlisted class pairs have count 0"])
        writer.writerow(["Actual class", "Predicted class", *keys])
        matrices = [{(actual, predicted): count for actual, predicted, count in nonzero_matrix(column["run"].result)}
                    for column in columns]
        pairs = sorted(set().union(*(set(matrix) for matrix in matrices)))
        for actual, predicted in pairs:
            writer.writerow([_csv_label(actual), _csv_label(predicted),
                             *(matrix.get((actual, predicted), 0) for matrix in matrices)])
    # BOM helps spreadsheet applications recognize Unicode labels correctly.
    return stream.getvalue().encode("utf-8-sig")


def report_pdf(report):
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40,
                                 topMargin=40, bottomMargin=42, title=f"Evaluation report {report['run_key']}")
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "ReportSans"
    styles.add(ParagraphStyle("ReportCell", fontName="ReportSans", fontSize=9, leading=13, spaceAfter=0))
    styles.add(ParagraphStyle("ClientEyebrow", fontName="ReportSansBold", fontSize=9, leading=13,
                              textColor=colors.HexColor("#176c85"), spaceAfter=10))
    styles.add(ParagraphStyle("ClientTitle", fontName="ReportSansBold", fontSize=27, leading=33,
                              textColor=colors.HexColor("#112a3a"), spaceAfter=8))
    styles.add(ParagraphStyle("ClientModel", fontName="ReportSans", fontSize=13, leading=19,
                              textColor=colors.HexColor("#516779"), spaceAfter=20))
    styles.add(ParagraphStyle("MetricValue", fontName="ReportSansBold", fontSize=21, leading=29,
                              textColor=colors.HexColor("#007e87")))
    styles.add(ParagraphStyle("ClientSmall", fontName="ReportSans", fontSize=8, leading=12,
                              textColor=colors.HexColor("#516779"), spaceAfter=8))
    glyphs = pdfmetrics.getFont("ReportSans").face.charToGlyph
    escaped_unicode = False

    def paragraph(value, style="ReportCell"):
        nonlocal escaped_unicode
        characters = []
        for char in str(value):
            if char in "\n\r\t" or ord(char) in glyphs:
                characters.append(char)
            else:
                escaped_unicode = True
                characters.append(f"\\u{ord(char):04x}" if ord(char) <= 0xffff else f"\\U{ord(char):08x}")
        return Paragraph(escape("".join(characters)).replace("\n", "<br/>"), styles[style])

    def table(headers, rows, widths=None):
        data = [[paragraph(cell) for cell in row] for row in [headers, *rows]]
        result = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitInRow=1)
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eef7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7d2df")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return result

    width = A4[0] - 80
    if report["detailed"]:
        story = [paragraph("Evaluation report", "Title"), paragraph(report["dataset_name"], "Normal"), Spacer(1, 12)]
        if report["placeholder"]:
            story.extend([paragraph("Placeholder baseline: these results do not describe the selected algorithm.", "Normal"), Spacer(1, 12)])
        for section in report["sections"]:
            story.extend([paragraph(section["title"], "Heading2"),
                          table(["Setting", "Value"], section["rows"], [width * 0.34, width * 0.66]), Spacer(1, 10)])
        story.extend([paragraph("Column profile", "Heading2"),
                      table(["Column", "Type", "Missing count", "Missing %"], report["profile"], [width / 4] * 4),
                      paragraph("Evaluation metrics", "Heading2"),
                      paragraph("Displayed values match the comparison table. Full stored values are also included.", "Normal"),
                      table(["Metric", "Displayed", "Stored value"], [(row["label"], row["display"], row["raw"]) for row in report["metrics"]], [width * 0.3, width * 0.25, width * 0.45])])
        if report["task"] == "classification":
            story.extend([paragraph("Confusion matrix", "Heading2"),
                          paragraph("Unlisted class pairs have count 0. Every non-zero count is listed below.", "Normal"),
                          paragraph("Class labels: " + json.dumps(report["labels"], ensure_ascii=False), "Normal"),
                          table(["Actual class", "Predicted class", "Count"], report["matrix_entries"], [width * 0.4, width * 0.4, width * 0.2])])
    else:
        # The client report uses concise results; the optional technical download retains full details.
        story = [paragraph("MODEL EVALUATOR / PERFORMANCE", "ClientEyebrow"),
                 paragraph("Evaluation report", "ClientTitle"),
                 paragraph(f"{report['algorithm']} · {report['task'].capitalize()}", "ClientModel")]
        if report["placeholder"]:
            story.append(paragraph("Placeholder baseline: these results do not describe the selected algorithm.", "Normal"))
        metric_cells = [[paragraph(metric["label"], "ClientEyebrow"),
                         paragraph(metric["display"], "MetricValue"),
                         paragraph(metric["description"], "ClientSmall")]
                        for metric in report["metrics"]]
        cards = LongTable([metric_cells], colWidths=[width / 4] * 4, hAlign="LEFT")
        cards.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e9f7f5")),
            ("LINEBELOW", (0, 0), (-1, -1), 2, colors.HexColor("#007e87")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ]))
        story.extend([cards, Spacer(1, 10),
                      paragraph("Scores describe held-out evaluation data. " + (
                          "Higher is better. Precision, recall and F1-score are weighted across classes."
                          if report["task"] == "classification" else
                          "Lower errors are better; higher R² is better. MSE uses squared target units."), "ClientSmall"),
                      paragraph("Evaluation scope", "Heading2"),
                      table(["Overview", "Value"], report["facts"], [width * 0.32, width * 0.68])])
        if report["features"] is not None:
            story.extend([paragraph("Fields used", "Heading2"), paragraph(", ".join(report["features"]) or "No input fields", "Normal")])
        if report["breakdown"]:
            story.extend([paragraph("Prediction breakdown", "Heading2"),
                          paragraph("Rows show actual outcomes; columns show predicted outcomes. Values are record counts.", "ClientSmall"),
                          table(["Actual / predicted", *report["labels"]],
                                [[row["label"], *row["values"]] for row in report["breakdown"]],
                                [width / (len(report["labels"]) + 1)] * (len(report["labels"]) + 1))])
        elif report["task"] == "classification":
            story.append(paragraph("The full class-by-class breakdown is available in the optional technical report.", "ClientSmall"))
    if escaped_unicode:
        story.insert(2, paragraph("Unicode escapes preserve characters that are not supported by the report font.", "Normal"))

    def footer(canvas, doc):
        canvas.setFont("ReportSans", 8)
        canvas.drawRightString(A4[0] - 40, 24, f"Page {doc.page}")

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
