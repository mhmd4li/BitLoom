# loominar/api/issues/stream.py
import csv
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set

from loominar import console

from .pagination import PAGE_SIZE_DEFAULT, _describe, fetch_issues_cursor

log = console.get_logger(__name__)

# One canonical row schema shared by the streamed CSVs and the in-memory Excel
# sheet, so every sheet in the merged workbook has the same columns and the
# aggregate summary counts a single taxonomy.
FIELDNAMES = [
    "Severity", "Type", "Status", "Message", "File", "Line",
    "Rule", "Author", "Created", "Updated", "Effort", "Key",
]

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return str(value)
    return value


def issue_to_row(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a Sonar issue into the canonical report row (raw severity)."""
    component = issue.get("component") or ""
    return {
        "Severity": _scalar(issue.get("severity")),
        "Type": _scalar(issue.get("type")),
        "Status": _scalar(issue.get("status")),
        "Message": _scalar(issue.get("message")),
        "File": component.split(":")[-1] if component else "",
        "Line": _scalar(issue.get("line")),
        "Rule": _scalar(issue.get("rule")),
        "Author": _scalar(issue.get("author")),
        "Created": _scalar(issue.get("creationDate")),
        "Updated": _scalar(issue.get("updateDate")),
        "Effort": _scalar(issue.get("effort")),
        "Key": _scalar(issue.get("key")),
    }


def bucket_label(filters: Dict[str, Any], index: int) -> str:
    """
    Short, unique, Excel-safe label for a bucket.

    The zero-padded index leads so that truncating to Excel's 31-character sheet
    name limit can never collide — the previous scheme truncated long, similar
    stems to the same 31 characters and crashed xlsxwriter with a duplicate
    worksheet name.
    """
    parts = [f"{index:03d}"]
    for key in ("severities", "types"):
        value = filters.get(key)
        if value:
            parts.append(str(value).replace(",", "-"))
    created_after = filters.get("createdAfter")
    if created_after:
        parts.append(str(created_after)[:10].replace("-", ""))
    label = _UNSAFE_NAME.sub("_", "_".join(parts))
    return label[:31]


def stream_filters_to_csv(
    client,
    project_key: str,
    filters: Dict[str, Any],
    out_dir: Path,
    page_size: int = PAGE_SIZE_DEFAULT,
    index: int = 0,
    seen: Optional[Set[str]] = None,
    expected_total: int = 0,
) -> Optional[str]:
    """
    Stream every issue matching `filters` to a CSV under out_dir/.loominar_temp/.

    Uses the creation-date cursor, so buckets larger than Sonar's 10k result
    window are fetched completely instead of dying on the first page past it.

    On a mid-stream failure the rows already written are kept and the path is
    still returned — a partial bucket is worth far more than the deleted file
    the previous implementation left behind.

    Returns the CSV path, or None if nothing was written.
    """
    temp_dir = Path(out_dir) / ".loominar_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    label = bucket_label(filters, index)
    out_path = temp_dir / f"{label}.csv"

    written = 0
    progress = console.ProgressReporter(
        f"Streaming {_describe(filters)}", total=expected_total, logger=log
    )

    # "w" (not "a"): a leftover file from an earlier run must not be appended to.
    try:
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            for issue in fetch_issues_cursor(client, filters, page_size=page_size, seen=seen):
                writer.writerow(issue_to_row(issue))
                written += 1
                progress.advance()
    except Exception as exc:
        log.error("Streaming %s failed after %d rows: %s", _describe(filters), written, exc)
        if written == 0:
            try:
                out_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        log.warning("Keeping the %d rows already written to %s.", written, out_path.name)
        return str(out_path)

    if written == 0:
        log.debug("No issues matched %s; no CSV written.", _describe(filters))
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    progress.done()
    log.debug("Wrote %s (%d rows)", out_path, written)
    return str(out_path)
