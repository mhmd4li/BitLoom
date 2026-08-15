import csv
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from loominar import console
from loominar.api.issues.stream import FIELDNAMES, issue_to_row

from .base_report import BaseReport, SEVERITY_MAP

log = console.get_logger(__name__)


def _normalize_severity(raw: str) -> str:
    if not raw:
        return ""
    return SEVERITY_MAP.get(str(raw).strip().upper(), raw)


class CsvReport(BaseReport):
    def generate(
        self,
        issues: List[Dict[str, Any]],
        quality_gate: Optional[Dict[str, Any]] = None,
        streamed_csvs: Optional[List[str]] = None,
        cleanup_temp: bool = True,
    ) -> Optional[str]:
        """
        Write a single CSV covering both in-memory issues and streamed buckets.

        Rows are streamed through rather than collected into a DataFrame, so a
        large project costs the same memory as a small one.
        """
        streamed_csvs = streamed_csvs or []
        if not issues and not streamed_csvs:
            log.info("No issues to write; skipping CSV export.")
            return None

        status = (quality_gate or {}).get("status", "Report")
        filename = self._build_filename(status)
        written = 0
        merged = 0

        with open(filename, "w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()

            for issue in issues or []:
                row = issue_to_row(issue)
                row["Severity"] = _normalize_severity(row["Severity"])
                writer.writerow(row)
                written += 1

            for raw_path in streamed_csvs:
                path = Path(raw_path)
                if not path.exists():
                    log.warning("Bucket file is missing and will be skipped: %s", raw_path)
                    continue
                with path.open("r", newline="", encoding="utf-8") as fh:
                    for row in csv.DictReader(fh):
                        row["Severity"] = _normalize_severity(row.get("Severity", ""))
                        writer.writerow(row)
                        written += 1
                merged += 1

        log.success("CSV report written: %s (%s issues)", filename, f"{written:,}")

        skipped = len(streamed_csvs) - merged
        if skipped:
            log.warning(
                "%d bucket file(s) were missing, so temporary files were kept for inspection.",
                skipped,
            )
        elif cleanup_temp and merged:
            temp_dir = Path(self.output_dir) / ".loominar_temp"
            try:
                if temp_dir.is_dir():
                    shutil.rmtree(temp_dir)
                    log.debug("Removed temporary bucket files: %s", temp_dir)
            except OSError as exc:
                log.warning("Could not remove temporary directory %s: %s", temp_dir, exc)

        return filename


# loominar/report/csv_report.py
# Simple, dependency-light export
