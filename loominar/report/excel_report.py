import csv
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import xlsxwriter

from loominar import console
from loominar.api.issues.stream import FIELDNAMES, issue_to_row

from .base_report import BaseReport, SEVERITY_COLORS, SEVERITY_MAP

log = console.get_logger(__name__)

# Columns are wide enough to read without hand-resizing.
_COLUMN_WIDTHS = {
    "Severity": 12, "Type": 15, "Status": 11, "Message": 70, "File": 40,
    "Line": 8, "Rule": 28, "Author": 24, "Created": 22, "Updated": 22,
    "Effort": 9, "Key": 24,
}


def _normalize_severity(raw: str) -> str:
    """Map a Sonar severity onto the report taxonomy, idempotently."""
    if not raw:
        return ""
    raw = str(raw).strip()
    if raw in SEVERITY_COLORS:  # already normalized
        return raw
    return SEVERITY_MAP.get(raw.upper(), raw)


class ExcelReport(BaseReport):

    # ---------- sheet helpers ----------

    def _unique_sheet_name(self, name: str, used: Set[str]) -> str:
        """
        Excel caps sheet names at 31 chars and forbids []:*?/\\.

        Truncating long, similar names to 31 chars used to produce duplicates,
        which makes xlsxwriter raise. A numeric suffix guarantees uniqueness.
        """
        original = name
        for ch in "[]:*?/\\'":
            name = name.replace(ch, "_")
        name = (name.strip() or "Sheet")[:31]
        candidate = name
        suffix = 1
        while candidate.lower() in used:
            tag = f"_{suffix}"
            candidate = f"{name[:31 - len(tag)]}{tag}"
            suffix += 1
        if candidate != original:
            log.debug("Sheet name '%s' adjusted to '%s' for Excel", original, candidate)
        used.add(candidate.lower())
        return candidate

    def _new_sheet(self, workbook, name: str, used: Set[str], header_fmt, headers: List[str]):
        ws = workbook.add_worksheet(self._unique_sheet_name(name, used))
        # In constant_memory mode column widths must be set before any row is
        # written to the sheet.
        for idx, header in enumerate(headers):
            ws.set_column(idx, idx, _COLUMN_WIDTHS.get(header, 18))
        ws.write_row(0, 0, headers, header_fmt)
        ws.freeze_panes(1, 0)
        return ws

    def _severity_format(self, workbook, fmt_cache: Dict[str, Any], severity: str):
        color = SEVERITY_COLORS.get(severity)
        if not color:
            return None
        if color not in fmt_cache:
            # Cached: the old code built one format object per row, which is the
            # main reason large workbooks took minutes and ballooned in memory.
            fmt_cache[color] = workbook.add_format({"bg_color": f"#{color}"})
        return fmt_cache[color]

    def _write_rows(self, workbook, ws, rows: Iterable[Dict[str, Any]], fmt_cache) -> Tuple[int, Counter, Counter]:
        sev_counter: Counter = Counter()
        type_counter: Counter = Counter()
        written = 0

        for row_idx, row in enumerate(rows, start=1):
            severity = _normalize_severity(row.get("Severity", ""))
            values = [row.get(h, "") for h in FIELDNAMES]
            values[0] = severity
            ws.write_row(row_idx, 0, values)

            sev_fmt = self._severity_format(workbook, fmt_cache, severity)
            if sev_fmt is not None:
                ws.write(row_idx, 0, severity, sev_fmt)

            if severity:
                sev_counter[severity] += 1
            issue_type = row.get("Type", "")
            if issue_type:
                type_counter[issue_type] += 1
            written += 1

        return written, sev_counter, type_counter

    def _write_csv_sheet(self, workbook, csv_path: Path, used: Set[str], header_fmt, fmt_cache):
        ws = self._new_sheet(workbook, csv_path.stem, used, header_fmt, FIELDNAMES)
        with csv_path.open("r", newline="", encoding="utf-8") as fh:
            return self._write_rows(workbook, ws, csv.DictReader(fh), fmt_cache)

    def _write_issues_sheet(self, workbook, issues, used: Set[str], header_fmt, fmt_cache):
        ws = self._new_sheet(workbook, "Issues", used, header_fmt, FIELDNAMES)
        return self._write_rows(workbook, ws, (issue_to_row(i) for i in issues), fmt_cache)

    # ---------- summary ----------

    def _write_summary_and_metadata(self, workbook, summary: Dict[str, Any], used: Set[str], header_fmt):
        sheet_name = self._unique_sheet_name("Summary", used)
        ws = workbook.add_worksheet(sheet_name)
        ws.set_column(0, 0, 24)
        ws.set_column(1, 1, 14)

        ws.write(0, 0, "Total Issues", header_fmt)
        ws.write(0, 1, summary.get("total", 0))

        by_sev = summary.get("by_severity") or {}
        # Report severities in a fixed, meaningful order rather than hash order.
        ordered_sev = [s for s in SEVERITY_COLORS if s in by_sev]
        ordered_sev += [s for s in by_sev if s not in SEVERITY_COLORS]

        ws.write(2, 0, "By Severity", header_fmt)
        first_sev_row = 3
        row = first_sev_row
        for sev in ordered_sev:
            ws.write(row, 0, sev)
            ws.write(row, 1, by_sev[sev])
            row += 1
        last_sev_row = row - 1

        by_type = summary.get("by_type") or {}
        row += 1
        ws.write(row, 0, "By Type", header_fmt)
        row += 1
        for issue_type, count in sorted(by_type.items(), key=lambda kv: -kv[1]):
            ws.write(row, 0, issue_type)
            ws.write(row, 1, count)
            row += 1

        # Charts are only meaningful when there is severity data to plot; the
        # old code emitted them unconditionally, producing an A4:A3 range.
        if ordered_sev:
            categories = [sheet_name, first_sev_row, 0, last_sev_row, 0]
            values = [sheet_name, first_sev_row, 1, last_sev_row, 1]
            points = [{"fill": {"color": f"#{SEVERITY_COLORS.get(s, '808080')}"}} for s in ordered_sev]

            chart_pie = workbook.add_chart({"type": "pie"})
            chart_pie.add_series({
                "name": "Issue Distribution by Severity",
                "categories": categories,
                "values": values,
                "points": points,
            })
            chart_pie.set_title({"name": "Severity Distribution"})
            ws.insert_chart("D2", chart_pie, {"x_offset": 25, "y_offset": 10})

            chart_bar = workbook.add_chart({"type": "column"})
            chart_bar.add_series({
                "name": "Issue Count by Severity",
                "categories": categories,
                "values": values,
                "points": points,
            })
            chart_bar.set_title({"name": "Severity Counts"})
            chart_bar.set_legend({"none": True})
            ws.insert_chart("D18", chart_bar, {"x_offset": 25, "y_offset": 10})

        meta_ws = workbook.add_worksheet(self._unique_sheet_name("Metadata", used))
        meta_ws.set_column(0, 0, 18)
        meta_ws.set_column(1, 1, 50)
        for r, (key, value) in enumerate(self._get_metadata().items()):
            meta_ws.write(r, 0, key, header_fmt)
            meta_ws.write(r, 1, value)

    # ---------- entry point ----------

    def generate(
        self,
        issues: List[Dict[str, Any]],
        quality_gate: Optional[Dict[str, Any]] = None,
        streamed_csvs: Optional[List[str]] = None,
        cleanup_temp: bool = True,
    ) -> Optional[str]:
        """
        Write one workbook containing every issue — in-memory, streamed, or both.

        Streamed buckets and in-memory issues share the same column schema, so
        the aggregate summary counts a single severity taxonomy across sheets.
        """
        streamed_csvs = streamed_csvs or []
        if not issues and not streamed_csvs:
            log.info("No issues to write; skipping Excel export.")
            return None

        status = (quality_gate or {}).get("status", "Report")
        filename = self._build_filename(status)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # constant_memory keeps peak RAM flat: rows are flushed to disk as they
        # are written instead of being held until close().
        workbook = xlsxwriter.Workbook(filename, {"constant_memory": True})
        used_names: Set[str] = set()
        fmt_cache: Dict[str, Any] = {}
        total_count = 0
        agg_sev: Counter = Counter()
        agg_type: Counter = Counter()
        merged_csvs: List[Path] = []

        if streamed_csvs:
            log.info("Merging %d streamed bucket(s) into %s", len(streamed_csvs), Path(filename).name)

        try:
            header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})

            for raw_path in streamed_csvs:
                path = Path(raw_path)
                if not path.exists():
                    log.warning("Bucket file is missing and will be skipped: %s", raw_path)
                    continue
                count, sev_counts, type_counts = self._write_csv_sheet(
                    workbook, path, used_names, header_fmt, fmt_cache
                )
                log.debug("Sheet from %s: %d rows", path.name, count)
                total_count += count
                agg_sev.update(sev_counts)
                agg_type.update(type_counts)
                merged_csvs.append(path)

            if issues:
                count, sev_counts, type_counts = self._write_issues_sheet(
                    workbook, issues, used_names, header_fmt, fmt_cache
                )
                log.debug("Sheet 'Issues': %d rows", count)
                total_count += count
                agg_sev.update(sev_counts)
                agg_type.update(type_counts)

            self._write_summary_and_metadata(
                workbook,
                {"total": total_count, "by_severity": dict(agg_sev), "by_type": dict(agg_type)},
                used_names,
                header_fmt,
            )
        finally:
            workbook.close()

        log.success("Excel report written: %s (%s issues)", filename, f"{total_count:,}")

        skipped = len(streamed_csvs) - len(merged_csvs)
        if skipped:
            log.warning(
                "%d bucket file(s) were missing, so temporary files were kept for inspection "
                "in %s", skipped, Path(self.output_dir) / ".loominar_temp",
            )
        elif cleanup_temp and merged_csvs:
            # Only remove temp files once they are safely inside the workbook.
            self._cleanup_temp()
        elif merged_csvs:
            log.info("Temporary bucket files kept in %s", Path(self.output_dir) / ".loominar_temp")

        return filename

    def _cleanup_temp(self):
        temp_dir = Path(self.output_dir) / ".loominar_temp"
        try:
            if temp_dir.is_dir():
                shutil.rmtree(temp_dir)
                log.debug("Removed temporary bucket files: %s", temp_dir)
        except OSError as exc:
            log.warning("Could not remove temporary directory %s: %s", temp_dir, exc)
