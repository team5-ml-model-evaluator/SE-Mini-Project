"""CSV upload validation for the Data Pipeline (MLE-F-010, MLE-F-011).

This is the real implementation behind the WebUI's dataset stand-in: the
WebUI only calls ``validate_csv`` and must keep the returned shape and the
rejection messages unchanged (PR #27). The structural checks run on the raw
text so a malformed file never reaches profiling; the profile itself is
produced by :func:`datasets.profiling.profile_text`.
"""
import csv
import io

from django.conf import settings

from .exceptions import DatasetRejected
from .profiling import profile_text

MIN_ROWS = 20
MIN_COLUMNS = 2
MISSING_TOKENS = {"", "na", "n/a", "nan", "null", "none"}


def validate_csv(uploaded):
    """Check an uploaded file and return its profile, or raise DatasetRejected."""
    name = uploaded.name or ""
    if not name.lower().endswith(".csv"):
        raise DatasetRejected(f"“{name}” is not a CSV file. Choose a file whose name ends in .csv.")

    limit = settings.MAX_UPLOAD_BYTES
    if uploaded.size > limit:
        size_mb = uploaded.size / (1024 * 1024)
        raise DatasetRejected(
            f"The file is {size_mb:.1f} MB and the limit is {limit // (1024 * 1024)} MB. "
            "Remove rows or columns, then upload it again."
        )

    raw = b"".join(uploaded.chunks())
    uploaded.seek(0)
    if b"\x00" in raw:
        raise DatasetRejected("This file contains binary data, not text. Export the data again as a CSV file.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DatasetRejected("The file is not UTF-8 text. Save it as “CSV UTF-8” and upload it again.")

    try:
        table = [row for row in csv.reader(io.StringIO(text, newline=""), strict=True) if row]
    except csv.Error as exc:
        raise DatasetRejected(f"The file is not well-formed CSV ({exc}). Fix the quoting and upload it again.")
    if not table:
        raise DatasetRejected("The file is empty. Upload a CSV with a header row and at least 20 data rows.")

    header, body = table[0], table[1:]
    if len(header) < MIN_COLUMNS:
        raise DatasetRejected(
            f"The file has {len(header)} column. At least {MIN_COLUMNS} are needed: "
            "one to predict and one or more features."
        )
    if any(not column.strip() for column in header):
        raise DatasetRejected("A column in the header row has no name. Give every column a name and upload again.")
    if len(set(header)) != len(header):
        raise DatasetRejected("Two columns share the same name. Rename one of them and upload again.")
    for line_number, row in enumerate(body, start=2):
        if len(row) != len(header):
            raise DatasetRejected(
                f"Row {line_number} has {len(row)} values but the header has {len(header)}. "
                "Make every row the same length and upload again."
            )
    if len(body) < MIN_ROWS:
        raise DatasetRejected(
            f"The file has {len(body)} data rows. At least {MIN_ROWS} are needed to train and test a model."
        )

    return profile_text(text)
