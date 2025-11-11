from .word_report import WordReport
from .excel_report import ExcelReport
from .csv_report import CsvReport

class ReportManager:
    def __init__(self, output_dir, project_key, fmt):
        self.output_dir = output_dir
        self.project_key = project_key
        self.format = fmt.lower()

    def generate(self, metrics, qg, issues):
        if self.format == "word":
            WordReport(self.output_dir, self.project_key, self.format).generate(metrics, qg, issues)
        elif self.format == "excel":
            ExcelReport(self.output_dir, self.project_key, self.format).generate(issues, qg)
        elif self.format == "csv":
            CsvReport(self.output_dir, self.project_key, self.format).generate(issues, qg)
        else:
            print("❌ Unsupported format. Choose: word / excel / csv")

# bitloom/report/report_manager.py
# A clean orchestrator to pick the correct report generator dynamically