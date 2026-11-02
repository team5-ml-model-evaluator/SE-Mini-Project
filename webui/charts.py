"""Metric-aware comparison bars; the accompanying table is the numeric equivalent."""
from decimal import Decimal

from .comparison import METRICS


def comparison_chart(comparison, metric=None):
    if comparison is None:
        return None
    task = comparison["task"]
    choices = METRICS[task]
    default = "accuracy" if task == "classification" else "rmse"
    key = metric if metric in dict(choices) else default
    row = next(row for row in comparison["rows"] if row["key"] == key)
    values = [Decimal(value) for value in row["values"]]
    low = Decimal(0) if task == "classification" else min(Decimal(0), min(values))
    high = Decimal(1) if task == "classification" else max(Decimal(0), max(values))
    span = high - low or Decimal(1)
    zero = -low / span * 100
    bars = []
    for column, value, display in zip(comparison["columns"], values, row["display_values"]):
        position = (min(value, Decimal(0)) - low) / span * 100
        width = abs(value) / span * 100
        bars.append({"label": column["algorithm"].label, "key": column["run"].job_key,
                     "display": display, "left": f"{max(Decimal(0), min(Decimal(100), position)):.2f}",
                     "width": f"{max(Decimal(0), min(Decimal(100), width)):.2f}"})
    higher = task == "classification" or key == "r2"
    best = max(values) if higher else min(values)
    leaders = [column["algorithm"].label for column, value in zip(comparison["columns"], values) if value == best]
    return {"metric": key, "label": row["label"], "choices": choices, "bars": bars,
            "higher": higher, "zero": f"{zero:.2f}", "leaders": ", ".join(leaders),
            "best_display": row["display_values"][values.index(best)], "tied": len(leaders) > 1}
