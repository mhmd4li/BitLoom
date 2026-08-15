from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loominar import console

from .base_client import BaseClient
from .issues.pagination import (
    ISSUES_ENDPOINT,
    PAGE_SIZE_DEFAULT,
    SONAR_RESULT_WINDOW,
    ProbeError,
    fetch_issues_cursor,
    probe_total,
)
from .issues.splitter import DEFAULT_SPLIT_DIMS, iter_split_filters
from .issues.stream import stream_filters_to_csv

log = console.get_logger(__name__)

# Sonar's hard result window. Not a tuning knob.
MAX_RESULTS = SONAR_RESULT_WINDOW

# ps is capped at 500 by Sonar. The 10k window applies to p * ps, so a smaller
# page size buys no extra headroom - it only multiplies the request count.
PAGE_SIZE = PAGE_SIZE_DEFAULT

# Above this many issues, buckets are streamed to disk instead of held in RAM
# and the report is forced to Excel (Word/CSV cannot render that volume).
INLINE_LIMIT = 10000


class IssuesClient(BaseClient):

    def base_filters(self, project_key: str) -> Dict[str, Any]:
        """
        The single filter set used for both counting and fetching.

        OPEN and CONFIRMED are unresolved by definition, so `resolved=false` was
        redundant - and because the old probe omitted `statuses` while the fetch
        included it, the total driving every split decision described a
        different result set than the one actually retrieved.
        """
        return {"componentKeys": project_key, "statuses": "OPEN,CONFIRMED"}

    def count_issues(self, project_key: str) -> int:
        """Total open issues. Raises ProbeError if the count cannot be read."""
        return probe_total(self, ISSUES_ENDPOINT, self.base_filters(project_key), required=True)

    def fetch_pages(self, filters: Dict[str, Any], seen: Optional[set] = None) -> List[Dict[str, Any]]:
        """Fetch every issue matching `filters` into memory."""
        return list(fetch_issues_cursor(self, filters, page_size=PAGE_SIZE, seen=seen))

    def _resolve_format(
        self, fmt: str, total: int, no_cnfrm: bool, large_warn: bool, inline_limit: int
    ) -> Tuple[str, bool]:
        """Apply the large-report fallback to Excel, prompting when allowed."""
        if fmt == "excel" or total <= inline_limit:
            return fmt, large_warn

        if no_cnfrm:
            log.warning(
                "%s issues exceed the %s-issue limit for %s output.\n"
                "Falling back to Excel, which can render this volume reliably.",
                f"{total:,}", f"{inline_limit:,}", fmt.upper(),
            )
            return "excel", large_warn

        log.warning(
            "%s issues found, more than the %s-issue limit for %s output.\n"
            "A %s report this large is slow to render and may not open.",
            f"{total:,}", f"{inline_limit:,}", fmt.upper(), fmt.upper(),
        )
        console.prompt(f"Continue with {fmt.capitalize()} export anyway? (y/N): ")
        try:
            choice = input().strip().lower()
        except EOFError:
            choice = ""
        large_warn = True
        if choice != "y":
            log.info("Switched to Excel export.")
            return "excel", large_warn
        log.info("Continuing with %s export at the user's request.", fmt.upper())
        return fmt, large_warn

    def get_all_issues(
        self,
        project_key: str,
        fmt: str,
        no_cnfrm: bool,
        output_dir: str,
        large_warn: bool = False,
        split_dims: Optional[List[str]] = None,
        inline_limit: int = INLINE_LIMIT,
    ):
        """
        Retrieve every open issue for `project_key`.

        Small projects are returned in memory. Large ones are split by severity
        (then type, then creation date) and streamed to per-bucket CSVs, which
        the Excel report merges - keeping memory flat regardless of project size.

        Returns (issues_in_memory, fmt, large_warn, streamed_csvs).
        """
        streamed_csvs: List[str] = []
        filters = self.base_filters(project_key)

        total = self.count_issues(project_key)
        if total == 0:
            log.info("Project '%s' has no open issues.", project_key)
            return [], fmt, large_warn, streamed_csvs

        log.info("Project '%s': %s open issues reported.", project_key, f"{total:,}")

        inline_limit = max(1, int(inline_limit or INLINE_LIMIT))
        fmt, large_warn = self._resolve_format(fmt, total, no_cnfrm, large_warn, inline_limit)

        # Deduplicate across every bucket: severity/type partition cleanly, but
        # date windows share an inclusive boundary and the cursor re-reads it.
        seen: set = set()

        # Excel and CSV can be assembled from streamed buckets without holding
        # the result set in RAM. Word cannot - python-docx builds the whole
        # document in memory - so a user who insists on Word past the warning
        # gets the in-memory path, cost and all.
        use_streaming = total > inline_limit and fmt in ("excel", "csv")

        if not use_streaming:
            if total > inline_limit:
                log.warning(
                    "Loading %s issues into memory for the %s report; this may be slow.",
                    f"{total:,}", fmt.upper(),
                )
            else:
                log.debug("Fetching %s issues into memory (limit %s).", f"{total:,}", f"{inline_limit:,}")

            issues = self.fetch_pages(filters, seen=seen)
            log.success("Retrieved %s unique issues.", f"{len(issues):,}")
            if len(issues) < total:
                log.warning(
                    "Retrieved %s of the %s reported issues; some pages did not return.\n"
                    "Re-run with -v 3 to see which requests failed.",
                    f"{len(issues):,}", f"{total:,}",
                )
            return issues, fmt, large_warn, streamed_csvs

        # Large project: split, then stream every bucket to disk.
        dims = split_dims or DEFAULT_SPLIT_DIMS
        log.info(
            "%s issues exceed the %s-issue inline limit. Splitting by %s and streaming to disk.",
            f"{total:,}", f"{inline_limit:,}", " then ".join(dims),
        )

        streamed_rows = 0
        for index, (bucket_filters, bucket_total) in enumerate(
            iter_split_filters(self, project_key, filters, split_dims, total), start=1
        ):
            if bucket_total > MAX_RESULTS:
                log.debug(
                    "Bucket %d exceeds the %s-result window (%s issues); using the creation-date cursor.",
                    index, f"{MAX_RESULTS:,}", f"{bucket_total:,}",
                )

            csv_path = stream_filters_to_csv(
                self,
                project_key,
                bucket_filters,
                Path(output_dir),
                page_size=PAGE_SIZE,
                index=index,
                seen=seen,
                expected_total=bucket_total,
            )
            if csv_path:
                streamed_csvs.append(csv_path)
                streamed_rows = len(seen)

        log.success(
            "Retrieved %s unique issues across %d buckets.",
            f"{streamed_rows:,}", len(streamed_csvs),
        )
        if streamed_rows < total:
            log.warning(
                "Retrieved %s of the %s issues reported at the start of the run.\n"
                "A small gap is normal (issues change state while the export runs); "
                "re-run if the difference is large.",
                f"{streamed_rows:,}", f"{total:,}",
            )
        for path in streamed_csvs:
            log.debug("Bucket file: %s", path)

        return [], fmt, large_warn, streamed_csvs


# Thin orchestrator: uses splitter, pagination, and stream helpers.
# Returns: (issues_in_memory, fmt, large_warn, streamed_csvs)
