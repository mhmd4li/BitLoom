from pathlib import Path
from .base_client import BaseClient
from .issues.pagination import fetch_all_pages
from .issues.splitter import iter_split_filters
from .issues.stream import stream_filters_to_csv

MAX_RESULTS = 10000
PAGE_SIZE = 500

class IssuesClient(BaseClient):

    def fetch_pages(self, filters, prefix=""):
        return list(fetch_all_pages(self, "/api/issues/search", filters, page_size=PAGE_SIZE))

    def get_all_issues(self, project_key, fmt, no_cnfrm, output_dir, large_warn=False):
        streamed_csvs = []
        all_issues = []

        try:
            first = self.get("/api/issues/search", {"componentKeys": project_key, "ps": 1, "p": 1, "resolved": "false"})
        except Exception as e:
            self._log(f"❌ Failed to probe issues for project {project_key}: {e}", 2, 1)
            return [], fmt, large_warn, streamed_csvs

        total = first.get("paging", {}).get("total", 0)
        self._log(f"📊 Total reported issues: {total}", 2, 1)

        # handle user confirmation / auto-switch (preserve previous UX)
        if not no_cnfrm:
            if fmt == "word" and total > MAX_RESULTS:
                self._log("\n⚠️  WARNING: More than 10,000 issues found.", 1, 2)
                choice = input("   Continue with Word export? (y/n): ").strip().lower()
                large_warn = True
                if choice != "y":
                    fmt = "excel"
                    self._log("   ✅ Switched to Excel export.", 1, 1)
        else:
            if fmt == "word" and total > MAX_RESULTS:
                self._log("\n⚠️  WARNING: Issue count exceeds 10,000. For reliability, the report will be generated in Excel format instead.", 1, 2)
                fmt = "excel"

        # small total: fetch in memory
        if total <= MAX_RESULTS:
            filters = {"componentKeys": project_key, "statuses": "OPEN,CONFIRMED", "resolved": "false"}
            all_issues.extend(fetch_all_pages(self, "/api/issues/search", filters, page_size=PAGE_SIZE))
            unique = {i["key"]: i for i in all_issues}
            return list(unique.values()), fmt, large_warn, streamed_csvs

        # large total -> splitter
        base_filters = {"componentKeys": project_key, "statuses": "OPEN,CONFIRMED", "resolved": "false"}
        for filters, chunk_total in iter_split_filters(self, project_key, base_filters, split_dims=["type", "component", "date"]):
            if chunk_total <= MAX_RESULTS:
                prefix = f"{filters.get('severities','all')}-{filters.get('types','all')}"
                self._log(f"🔹 Fetching chunk {prefix}: {chunk_total} issues", 2, 1)
                all_issues.extend(fetch_all_pages(self, "/api/issues/search", filters, page_size=PAGE_SIZE))
            else:
                self._log(f"⚠ Streaming large chunk to CSV: {filters} ({chunk_total} issues)", 1, 1)
                csv_path = stream_filters_to_csv(self, project_key, filters, Path(output_dir), page_size=PAGE_SIZE)
                if csv_path:
                    streamed_csvs.append(csv_path)

        unique = {i["key"]: i for i in all_issues}
        self._log(f"\n✅ Total unique issues fetched (in-memory): {len(unique)}", 1, 1)

        if streamed_csvs:
            self._log("⚠ Some buckets were streamed to CSV for later import/merging.", 1, 1)

        return list(unique.values()), fmt, large_warn, streamed_csvs


# Thin orchestrator: uses splitter, pagination, and stream helpers.
# Returns: (issues_in_memory, fmt, large_warn, streamed_csvs)

