from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple


def _as_date(value) -> date:
    """Accept a date, a datetime, or a Sonar ISO timestamp and return a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("empty date")
    # Sonar returns e.g. 2024-03-11T08:21:44+0000 — normalise the offset and
    # fall back to the leading date if the offset form is still unparseable.
    if len(text) > 5 and (text[-5] in "+-") and text[-5:].isalnum() and ":" not in text[-5:]:
        text = f"{text[:-5]}{text[-5:-2]}:{text[-2:]}"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return date.fromisoformat(text[:10])


def _add_month(d: date) -> date:
    """First day of the month following `d`'s month."""
    return date(d.year + (d.month // 12), (d.month % 12) + 1, 1)


def month_windows(start, end=None) -> List[Tuple[str, str]]:
    """
    Contiguous calendar-month windows covering [start, end].

    Windows are half-open — each window's `createdBefore` is the next window's
    `createdAfter` — so they tile the range without gaps. Sonar treats
    `createdAfter` as inclusive, so the shared boundary can repeat an issue;
    callers deduplicate by issue key.
    """
    start_d = _as_date(start)
    end_d = _as_date(end) if end is not None else datetime.now(timezone.utc).date()
    if end_d < start_d:
        start_d, end_d = end_d, start_d

    windows: List[Tuple[str, str]] = []
    cursor = date(start_d.year, start_d.month, 1)
    # `createdBefore` is exclusive of later times on the same day in some Sonar
    # versions; pad the final bound by a day so today's issues are never cut off.
    final = end_d + timedelta(days=1)

    while cursor < final:
        nxt = min(_add_month(cursor), final)
        windows.append((cursor.isoformat(), nxt.isoformat()))
        cursor = nxt
    return windows


def monthly_windows(now: datetime = None, months: int = 12) -> List[Tuple[str, str]]:
    """
    Backwards-compatible wrapper: the last `months` calendar months, oldest first.

    Prefer `month_windows(earliest, latest)` — anchoring on the project's real
    first issue date, because a fixed horizon silently drops older issues.
    """
    end_d = (now or datetime.now(timezone.utc)).date()
    start_d = end_d
    for _ in range(max(1, months) - 1):
        start_d = date(start_d.year, start_d.month, 1) - timedelta(days=1)
    return month_windows(date(start_d.year, start_d.month, 1), end_d)


def iso_midpoint(start_iso: str, end_iso: str) -> Optional[str]:
    """
    Midpoint of [start, end) as an ISO date, or None when the range is too
    narrow to split further (a single day) — which stops callers from recursing
    forever on a midpoint equal to one of the bounds.
    """
    s = _as_date(start_iso)
    e = _as_date(end_iso)
    if (e - s).days <= 1:
        return None
    mid = s + (e - s) / 2
    if isinstance(mid, datetime):
        mid = mid.date()
    if mid <= s or mid >= e:
        return None
    return mid.isoformat()


def earliest_issue_date(client, base_filters: dict) -> Optional[str]:
    """
    Creation date of the oldest issue matching `base_filters`, as an ISO date.
    Returns None when the project has no issues or the probe fails.
    """
    try:
        data = client.get(
            "/api/issues/search",
            {**base_filters, "ps": 1, "p": 1, "s": "CREATION_DATE", "asc": "true"},
        )
    except Exception:
        return None
    issues = (data or {}).get("issues") or []
    if not issues:
        return None
    created = issues[0].get("creationDate")
    if not created:
        return None
    try:
        return _as_date(created).isoformat()
    except ValueError:
        return None


# Date-window helpers for splitting oversized issue queries.
