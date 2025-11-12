import pandas as pd
from .base_report import BaseReport, SEVERITY_MAP
import console as c

class CsvReport(BaseReport):
    def generate(self, issues, quality_gate):
        if not issues:
            c.info("ℹ️ No issues found. Skipping CSV export.")
            return

        status = quality_gate.get("status", "Report")
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
        df.to_csv(filename, index=False)
        c.success(f"✅ CSV report saved: {filename}")

# loominar/report/csv_report.py
# Simple, dependency-light export