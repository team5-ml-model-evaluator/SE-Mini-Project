"""Bound confusion-matrix presentation work while keeping every stored cell accessible."""

MATRIX_PAGE_SIZE = 20


def _page_number(value, page_count):
    try:
        return max(1, min(int(value), page_count))
    except (ValueError, TypeError):
        return 1


def matrix_window(result, row_page=1, col_page=1):
    """Return at most 20 actual classes by 20 predicted classes; never copy the full matrix."""
    labels = result.get("labels") or []
    matrix = result.get("confusion_matrix") or []
    class_count = len(labels)
    page_count = max(1, (class_count + MATRIX_PAGE_SIZE - 1) // MATRIX_PAGE_SIZE)
    row_page = _page_number(row_page, page_count)
    col_page = _page_number(col_page, page_count)
    row_start, col_start = (row_page - 1) * MATRIX_PAGE_SIZE, (col_page - 1) * MATRIX_PAGE_SIZE
    row_end = min(row_start + MATRIX_PAGE_SIZE, class_count)
    col_end = min(col_start + MATRIX_PAGE_SIZE, class_count)
    rows = []
    for i in range(row_start, min(row_end, len(matrix))):
        values = matrix[i][col_start:col_end]
        rows.append({"label": labels[i], "values": values,
                     "cells": [{"value": value, "correct": col_start + j == i}
                               for j, value in enumerate(values)]})
    return {
        "labels": labels[col_start:col_end], "rows": rows, "class_count": class_count,
        "paginated": class_count > MATRIX_PAGE_SIZE, "page_count": page_count,
        "row_page": row_page, "col_page": col_page,
        "row_start": row_start + 1, "row_end": row_end,
        "col_start": col_start + 1, "col_end": col_end,
        "previous_row": row_page - 1 if row_page > 1 else None,
        "next_row": row_page + 1 if row_page < page_count else None,
        "previous_col": col_page - 1 if col_page > 1 else None,
        "next_col": col_page + 1 if col_page < page_count else None,
    }
