"""Use the same metric presentation on run pages, reports and comparisons."""
import math

from django import template

from webui.comparison import METRICS, format_metric

register = template.Library()


@register.filter
def metric_display(value, task):
    """Keep missing or invalid saved scores distinct from an actual zero."""
    if task not in METRICS or type(value) not in (int, float):
        return "—"
    try:
        return format_metric(task, value) if math.isfinite(value) else "—"
    except (ArithmeticError, ValueError):
        return "—"
