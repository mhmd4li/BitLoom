import time
from .base_client import BaseClient
from .utils import render_progress

MAX_RESULTS = 10000
PAGE_SIZE = 500
SEVERITIES = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
TYPES = ["BUG", "VULNERABILITY", "CODE_SMELL"]

class IssuesClient(BaseClient):
    def get_all_issues(self, project_key, fmt, no_cnfrm):
        all_issues = []

        def fetch_segment(filters, prefix=""):
            page = 1
            segment_issues = []
            total = None

            while True:
                params = filters.copy()
                params["ps"] = PAGE_SIZE
                params["p"] = page
                data = self.get("/api/issues/search", params)
                issues = data.get("issues", [])
                if not issues:
                    break

                segment_issues.extend(issues)
                total = data.get("paging", {}).get("total", 0)

                if self.verbosity >= 2:
                    render_progress(len(segment_issues), total, prefix=prefix)

                if len(segment_issues) >= total:
                    break
                page += 1

            if self.verbosity >= 2:
                render_progress(total, total, prefix=prefix)
            return segment_issues

        # Initial count
        first = self.get("/api/issues/search", {"componentKeys": project_key, "ps": 1, "p": 1})
        total = first.get("paging", {}).get("total", 0)
        self._log(f"📊 Total reported issues: {total}", 2)

        # Handle large datasets based on execution mode: prompt in interactive mode, auto-switch to Excel in CLI mode.
        if no_cnfrm == False:
            if fmt == "word" and total > MAX_RESULTS:
                self._log("\n⚠️  WARNING: More than 10,000 issues found.", 1)
                choice = input("   Continue with Word export? (y/n): ").strip().lower()
                if choice != "y":
                    fmt = "excel"
                    self._log("   ✅ Switched to Excel export.", 1)
        else:
            if fmt == "word" and total > MAX_RESULTS:
                self._log("\n⚠️  WARNING: Issue count exceeds 10,000. For reliability, the report will be generated in Excel format instead.", 1)
                fmt = "excel"

        if total <= MAX_RESULTS:
            all_issues.extend(fetch_segment({
                "componentKeys": project_key,
                "statuses": "OPEN,CONFIRMED"
            }, prefix="ALL"))
            return all_issues, fmt

        # Split by severity/type
        self._log("⚙️  Splitting by severity/type due to large dataset...", 2)
        for sev in SEVERITIES:
            params = {"componentKeys": project_key, "statuses": "OPEN,CONFIRMED", "severities": sev}
            sev_total = self.get("/api/issues/search", {**params, "ps": 1, "p": 1}).get("paging", {}).get("total", 0)
            if sev_total == 0:
                continue
            self._log(f"🔹 {sev}: {sev_total} issues", 2)

            if sev_total <= MAX_RESULTS:
                all_issues.extend(fetch_segment(params, prefix=f"{sev}"))
            else:
                for t in TYPES:
                    t_params = {**params, "types": t}
                    sub_total = self.get("/api/issues/search", {**t_params, "ps": 1, "p": 1}).get("paging", {}).get("total", 0)
                    if sub_total == 0:
                        continue
                    self._log(f"  🔸 {sev}-{t}: {sub_total} issues", 2)
                    all_issues.extend(fetch_segment(t_params, prefix=f"{sev}-{t}"))

        unique = {i["key"]: i for i in all_issues}
        self._log(f"\n✅ Total unique issues fetched: {len(unique)}", 1)
        return list(unique.values()), fmt
    

# loominar/api/issues_client.py
# Issue fetching, pagination, progress bar
# Issues, Pagination, and Progress
# This is where progress bars and dataset warnings live
