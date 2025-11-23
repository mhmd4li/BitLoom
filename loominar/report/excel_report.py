import csv
import shutil
from pathlib import Path
from collections import Counter
from typing import Iterable, List, Dict, Any, Optional

import pandas as pd
import xlsxwriter

from .base_report import BaseReport, SEVERITY_MAP, SEVERITY_COLORS
from loominar import console as c


def _normalize_severity(raw: str) -> str:
    if not raw:
        return ""
    # Try direct mapping first (assumes Sonar severity uppercase)
    normalized = SEVERITY_MAP.get(raw, None)
    if normalized:
        return normalized
    # Try common variants
    return SEVERITY_MAP.get(raw.upper(), raw)


class ExcelReport(BaseReport):
    def _write_summary_and_metadata_and_charts(self, workbook: xlsxwriter.Workbook, summary: Dict[str, Any]):
        """
        Adds Summary, Metadata and charts to the workbook using the provided summary dict.
        summary format: {"total": int, "by_severity": {str: int}, "by_type": {str:int}}
        """
        summary_ws = workbook.add_worksheet("Summary")

        # Total
        summary_ws.write("A1", "Total Issues")
        summary_ws.write("B1", summary.get("total", 0))

        # By severity
        summary_ws.write("A3", "By Severity")
        row = 4
        by_sev = summary.get("by_severity", {})
        for sev, count in by_sev.items():
            summary_ws.write(f"A{row}", sev)
            summary_ws.write(f"B{row}", count)
            row += 1

        # By type (optional, placed below severity)
        start_type_row = row + 1
        summary_ws.write(f"A{start_type_row}", "By Type")
        tr = start_type_row + 1
        for t, count in summary.get("by_type", {}).items():
            summary_ws.write(f"A{tr}", t)
            summary_ws.write(f"B{tr}", count)
            tr += 1

        # Pie chart - uses severity rows A4:B{row-1}
        if by_sev:
            chart_pie = workbook.add_chart({"type": "pie"})
            chart_pie.add_series({
                "categories": f"=Summary!$A$4:$A${row-1}",
                "values": f"=Summary!$B$4:$B${row-1}",
                "name": "Issue Distribution by Severity"
            })
            chart_pie.set_title({"name": "Severity Distribution"})
            summary_ws.insert_chart("D2", chart_pie, {"x_offset": 25, "y_offset": 10})

            # Bar chart
            chart_bar = workbook.add_chart({"type": "column"})
            chart_bar.add_series({
                "categories": f"=Summary!$A$4:$A${row-1}",
                "values": f"=Summary!$B$4:$B${row-1}",
                "name": "Issue Count by Severity"
            })
            chart_bar.set_title({"name": "Severity Counts"})
            summary_ws.insert_chart("D18", chart_bar, {"x_offset": 25, "y_offset": 10})

        # Metadata sheet
        metadata_ws = workbook.add_worksheet("Metadata")
        meta = self._get_metadata()
        r = 0
        for k, v in meta.items():
            metadata_ws.write(r, 0, k)
            metadata_ws.write(r, 1, v)
            r += 1

        header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2"})
        metadata_ws.set_column("A:A", 18, header_fmt)
        metadata_ws.set_column("B:B", 50)

    def _write_csv_to_sheet(self, workbook: xlsxwriter.Workbook, csv_path: Path):
        """
        Read csv via DictReader to preserve headers and also return severity/type counters.
        """
        sheet_name = csv_path.stem[:31]  # Excel limit
        ws = workbook.add_worksheet(sheet_name)

        sev_counter = Counter()
        type_counter = Counter()
        total_rows = 0

        with csv_path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
            # write header
            ws.write_row(0, 0, headers)
            # write rows and accumulate counts
            for r_idx, row in enumerate(reader, start=1):
                row_vals = [row.get(h, "") for h in headers]
                ws.write_row(r_idx, 0, row_vals)
                # severity detection (try common header names)
                sev_raw = row.get("Severity") or row.get("severity") or row.get("severityName") or row.get("severity_level") or ""
                sev = _normalize_severity(sev_raw)
                if sev:
                    sev_counter[sev] += 1
                t = row.get("Type") or row.get("type") or ""
                if t:
                    type_counter[t] += 1
                total_rows += 1

        return total_rows, sev_counter, type_counter

    def _write_in_memory_issues_sheet(self, workbook: xlsxwriter.Workbook, issues: Iterable[Dict[str, Any]]):
        """
        Writes in-memory issues to a worksheet named 'InMemory_Issues' and returns counters.
        Preserves the same columns used previously in your DataFrame mapping.
        """
        issues = list(issues)
        if not issues:
            return 0, Counter(), Counter()

        ws = workbook.add_worksheet("InMemory_Issues")
        # Reuse the same mapping you had for the DataFrame
        headers = ["Severity", "Type", "Message", "File", "Line"]
        ws.write_row(0, 0, headers)
        sev_counter = Counter()
        type_counter = Counter()

        for r_idx, i in enumerate(issues, start=1):
            sev_norm = _normalize_severity(i.get("severity", ""))
            row = [
                sev_norm,
                i.get("type", ""),
                i.get("message", ""),
                i.get("component", "").split(":")[-1],
                i.get("line", "")
            ]
            ws.write_row(r_idx, 0, row)
            if sev_norm:
                sev_counter[sev_norm] += 1
            t = i.get("type", "")
            if t:
                type_counter[t] += 1

        # Color severity column (column A) similar to your old logic
        for row_idx in range(1, len(issues) + 1):
            sev = ws.table = None  # noop to keep linter happy; coloring done separately below

        # apply per-cell coloring for severity column
        for r_idx, i in enumerate(issues, start=2):
            sev = _normalize_severity(i.get("severity", ""))
            color = SEVERITY_COLORS.get(sev, "FFFFFF")
            fmt = workbook.add_format({"bg_color": f"#{color}"})
            ws.write(f"A{r_idx}", sev, fmt)

        return len(issues), sev_counter, type_counter

    def generate(self, issues: List[Dict[str, Any]], quality_gate: Dict[str, Any], streamed_csvs: Optional[List[str]] = None, cleanup_temp: bool = True):
        """
        If streamed_csvs provided (list of CSV file paths), import them into an xlsx workbook,
        add an InMemory_Issues sheet (if issues not empty), then generate Summary/Metadata/charts.
        Otherwise use the existing small-run pandas -> xlsxwriter behavior.
        """
        # If no issues and no streamed CSVs -> nothing to do
        if not issues and not streamed_csvs:
            c.info("ℹ️ No issues found. Skipping Excel export.")
            return

        # If streamed CSVs are provided, create workbook and merge
        if streamed_csvs:
            # build filename and ensure xlsx extension
            filename = Path(self._build_filename()).with_suffix(".xlsx")
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)

            # create workbook with constant_memory for low memory usage
            workbook = xlsxwriter.Workbook(str(filename), {'constant_memory': True})
            total_count = 0
            agg_sev = Counter()
            agg_type = Counter()

            try:
                # write each CSV as its own sheet, and aggregate counts
                for csv_path in streamed_csvs:
                    path = Path(csv_path)
                    if not path.exists():
                        self._log(f"⚠ Streamed CSV not found: {csv_path}", 1, 1)
                        continue
                    cnt, sev_c, type_c = self._write_csv_to_sheet(workbook, path)
                    total_count += cnt
                    agg_sev.update(sev_c)
                    agg_type.update(type_c)

                # write in-memory issues into its own sheet and aggregate
                if issues:
                    cnt_mem, sev_c_mem, type_c_mem = self._write_in_memory_issues_sheet(workbook, issues)
                    total_count += cnt_mem
                    agg_sev.update(sev_c_mem)
                    agg_type.update(type_c_mem)

                # build summary structure
                summary = {
                    "total": total_count,
                    "by_severity": dict(agg_sev),
                    "by_type": dict(agg_type)
                }

                # write summary, metadata and charts
                self._write_summary_and_metadata_and_charts(workbook, summary)

            finally:
                workbook.close()

            c.success(f"✅ Excel report saved: {filename}")

            # cleanup of temp CSVs under output_dir/.loominar_temp/
            # cleanup_temp is set to True to remove temp files after merging
            if cleanup_temp and streamed_csvs:
                temp_dir = Path(self.output_dir) / ".loominar_temp"
                try:
                    if temp_dir.exists() and temp_dir.is_dir():
                        shutil.rmtree(temp_dir)
                        self._log(f"🧹 Removed temporary CSVs: {temp_dir}", 1, 1)
                except Exception as e:
                    self._log(f"⚠ Failed to remove temp dir {temp_dir}: {e}", 1, 1)
            return str(filename)

        # --- fallback: original small-run logic (unchanged) ---
        # Use original DataFrame mapping and formatting for small datasets
        if not issues:
            c.info("ℹ️ No issues found. Skipping Excel export.")
            return

        status = quality_gate.get("status", "Report")
        summary = self._build_summary(issues)

        df = pd.DataFrame([
            {
                "Severity": SEVERITY_MAP.get(i.get("severity", ""), i.get("severity", "")),
                "Type": i.get("type", ""),
                "Message": i.get("message", ""),
                "File": i.get("component", "").split(":")[-1],
                "Line": i.get("line", "")
            }
            for i in issues
        ])

        filename = self._build_filename(status)

        with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Issues")

            workbook = writer.book
            ws = writer.sheets["Issues"]

            # Color severity column
            for row_idx, sev in enumerate(df["Severity"], start=2):
                color = SEVERITY_COLORS.get(sev, "FFFFFF")
                fmt = workbook.add_format({"bg_color": f"#{color}"})
                ws.write(f"A{row_idx}", sev, fmt)

            summary_ws = workbook.add_worksheet("Summary")
            summary_ws.write("A1", "Total Issues")
            summary_ws.write("B1", summary["total"])

            summary_ws.write("A3", "By Severity")
            row = 4
            for sev, count in summary["by_severity"].items():
                summary_ws.write(f"A{row}", sev)
                summary_ws.write(f"B{row}", count)
                row += 1

            # Pie chart
            chart_pie = workbook.add_chart({"type": "pie"})
            chart_pie.add_series({
                "categories": f"=Summary!$A$4:$A${row-1}",
                "values": f"=Summary!$B$4:$B${row-1}",
                "name": "Issue Distribution by Severity"
            })
            chart_pie.set_title({"name": "Severity Distribution"})
            summary_ws.insert_chart("D2", chart_pie, {"x_offset": 25, "y_offset": 10})

            # Bar chart
            chart_bar = workbook.add_chart({"type": "column"})
            chart_bar.add_series({
                "categories": f"=Summary!$A$4:$A${row-1}",
                "values": f"=Summary!$B$4:$B${row-1}",
                "name": "Issue Count by Severity"
            })
            chart_bar.set_title({"name": "Severity Counts"})
            summary_ws.insert_chart("D18", chart_bar, {"x_offset": 25, "y_offset": 10})

            metadata_ws = workbook.add_worksheet("Metadata")
            meta = self._get_metadata()
            row = 0
            for k, v in meta.items():
                metadata_ws.write(row, 0, k)
                metadata_ws.write(row, 1, v)
                row += 1

            header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9E1F2"})
            metadata_ws.set_column("A:A", 18, header_fmt)
            metadata_ws.set_column("B:B", 50)

        c.success(f"✅ Excel report saved: {filename}")
