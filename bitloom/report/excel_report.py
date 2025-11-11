import pandas as pd
from .base_report import BaseReport, SEVERITY_MAP, SEVERITY_COLORS

class ExcelReport(BaseReport):
    def generate(self, issues, quality_gate):
        if not issues:
            print("ℹ️ No issues found. Skipping Excel export.")
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

        print(f"✅ Excel report saved: {filename}")


# bitloom/report/excel_report.py
# Includes summary sheet and colored severity column.