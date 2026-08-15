"""
Progress helpers.

The bar-drawing implementation that used to live here wrote directly to stdout
with block glyphs, which corrupted piped output and rendered as mojibake in CI
logs. Progress is now a logging concern, handled by console.ProgressReporter,
so it obeys verbosity, goes to stderr, and throttles itself on elapsed time.
"""

from loominar import console

log = console.get_logger(__name__)

ProgressReporter = console.ProgressReporter


def render_progress(current, total, prefix="", logger=None):
    """
    Log a single progress line.

    Kept for callers that only have a current/total pair. Prefer
    ``console.ProgressReporter`` for loops: it throttles, and it reports rate.
    """
    total = max(int(total or 0), 1)
    current = max(int(current or 0), 0)
    percent = min(100.0, current * 100.0 / total)
    (logger or log).info(
        "%s%s/%s (%.0f%%)", f"{prefix}: " if prefix else "", f"{current:,}", f"{total:,}", percent
    )


# loominar/api/utils.py
# Progress reporting, delegated to the console logger.
