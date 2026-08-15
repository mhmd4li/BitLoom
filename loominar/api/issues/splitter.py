# loominar/api/issues/splitter.py
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .components import list_components
from .date_utils import earliest_issue_date, iso_midpoint, month_windows
from .pagination import ISSUES_ENDPOINT, SONAR_RESULT_WINDOW, probe_total

MAX_RESULTS = SONAR_RESULT_WINDOW

# Severity is the primary split: every issue carries exactly one, so the buckets
# partition the result set cleanly with no gaps and no overlap.
SEVERITIES = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
TYPES = ["BUG", "VULNERABILITY", "CODE_SMELL"]

# `component` is deliberately not a default dimension: directory keys nest, so
# the buckets overlap, and issues on the project component itself fall through
# the gaps. Callers can opt into it explicitly.
DEFAULT_SPLIT_DIMS = ["severity", "type", "date"]

# Depth guard for the binary date split (2^12 ≈ sub-hour windows).
_MAX_DATE_DEPTH = 12


def _split_date_range(
    client,
    project_key: str,
    base_filters: Dict[str, Any],
    start_iso: str,
    end_iso: str,
    rest: List[str],
    depth: int = 0,
) -> Iterator[Tuple[Dict[str, Any], int]]:
    """Halve [start, end) until each window fits the result window."""
    filters = {**base_filters, "createdAfter": start_iso, "createdBefore": end_iso}
    total = probe_total(client, ISSUES_ENDPOINT, filters)
    if total == 0:
        return
    if total <= MAX_RESULTS:
        yield filters, total
        return

    mid = iso_midpoint(start_iso, end_iso) if depth < _MAX_DATE_DEPTH else None
    if mid is None:
        # Cannot narrow by date any further. Try the remaining dimensions;
        # otherwise emit it oversized — the cursor fetcher handles that case.
        if rest:
            yield from iter_split_filters(client, project_key, filters, rest, total)
        else:
            yield filters, total
        return

    yield from _split_date_range(client, project_key, base_filters, start_iso, mid, rest, depth + 1)
    yield from _split_date_range(client, project_key, base_filters, mid, end_iso, rest, depth + 1)


def iter_split_filters(
    client,
    project_key: str,
    base_filters: Dict[str, Any],
    split_dims: Optional[List[str]] = None,
    total: Optional[int] = None,
) -> Iterator[Tuple[Dict[str, Any], int]]:
    """
    Yield (filters, total) buckets that together cover `base_filters`.

    Each bucket is narrowed until it fits inside Sonar's 10k result window, or
    until no split dimension is left — an oversized bucket is still yielded, and
    the caller's cursor-based fetcher will page through it correctly.

    Buckets are yielded exactly once; `base_filters` itself is never re-yielded
    after being split, which would duplicate the entire result set.
    """
    if split_dims is None:
        split_dims = list(DEFAULT_SPLIT_DIMS)

    if total is None:
        total = probe_total(client, ISSUES_ENDPOINT, base_filters)

    if total == 0:
        return
    if total <= MAX_RESULTS or not split_dims:
        yield base_filters, total
        return

    dim, rest = split_dims[0], split_dims[1:]

    if dim == "severity":
        for sev in SEVERITIES:
            filters = {**base_filters, "severities": sev}
            sub_total = probe_total(client, ISSUES_ENDPOINT, filters)
            if sub_total == 0:
                continue
            yield from iter_split_filters(client, project_key, filters, rest, sub_total)
        return

    if dim == "type":
        for typ in TYPES:
            filters = {**base_filters, "types": typ}
            sub_total = probe_total(client, ISSUES_ENDPOINT, filters)
            if sub_total == 0:
                continue
            yield from iter_split_filters(client, project_key, filters, rest, sub_total)
        return

    if dim == "component":
        components = list_components(client, project_key)
        if not components:
            yield from iter_split_filters(client, project_key, base_filters, rest, total)
            return
        for comp in components:
            filters = {**base_filters, "componentKeys": comp}
            sub_total = probe_total(client, ISSUES_ENDPOINT, filters)
            if sub_total == 0:
                continue
            yield from iter_split_filters(client, project_key, filters, rest, sub_total)
        return

    if dim == "date":
        # Anchor on the project's oldest issue rather than a fixed horizon —
        # a rolling 12-month window silently drops everything older.
        start = base_filters.get("createdAfter") or earliest_issue_date(client, base_filters)
        if not start:
            yield from iter_split_filters(client, project_key, base_filters, rest, total)
            return

        windows = month_windows(start, base_filters.get("createdBefore"))
        if not windows:
            yield from iter_split_filters(client, project_key, base_filters, rest, total)
            return

        for start_iso, end_iso in windows:
            yield from _split_date_range(client, project_key, base_filters, start_iso, end_iso, rest)
        return

    # Unknown dimension — skip it rather than dropping the bucket.
    yield from iter_split_filters(client, project_key, base_filters, rest, total)


# Yield (filters, total) pairs. Recursively split filters until each bucket <= MAX_RESULTS.
# Splitting order (default): severity -> type -> date
