"""The linear workflow of SRS section 3.1, with the current stage always visible."""

STAGES = [("dataset", "Dataset"), ("pipeline", "Pipeline"), ("model", "Model"), ("run", "Run"), ("results", "Results")]


def stage_list(current):
    """Return the stages with a ``status`` of done, current or upcoming (shown as text, not colour)."""
    keys = [key for key, _ in STAGES]
    position = keys.index(current)
    out = []
    for index, (key, label) in enumerate(STAGES):
        status = "done" if index < position else "current" if index == position else "upcoming"
        out.append({"key": key, "label": label, "number": index + 1, "status": status})
    return out
