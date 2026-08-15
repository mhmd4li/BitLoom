from loominar import console

from .csv_report import CsvReport
from .excel_report import ExcelReport
from .word_report import WordReport

log = console.get_logger(__name__)

SUPPORTED_FORMATS = ("word", "excel", "csv")


class ReportManager:
    def __init__(self, output_dir, project_key, fmt, verbosity=2, keep_temp=False):
        self.output_dir = output_dir
        self.project_key = project_key
        self.format = (fmt or "").lower().strip()
        self.verbosity = verbosity
        self.keep_temp = keep_temp

    def generate(self, metrics, qg, issues, streamed_csvs=None):
        streamed_csvs = streamed_csvs or []

        if self.format not in SUPPORTED_FORMATS:
            log.error(
                "Unsupported output format '%s'. Choose one of: %s.",
                self.format, ", ".join(SUPPORTED_FORMATS),
            )
            return None

        log.debug(
            "Generating %s report: %d in-memory issues, %d streamed bucket(s)",
            self.format.upper(), len(issues or []), len(streamed_csvs),
        )

        args = (self.output_dir, self.project_key, self.format, self.verbosity)
        cleanup = not self.keep_temp

        if self.format == "excel":
            return ExcelReport(*args).generate(issues, qg, streamed_csvs, cleanup_temp=cleanup)

        if self.format == "csv":
            return CsvReport(*args).generate(issues, qg, streamed_csvs, cleanup_temp=cleanup)

        # Word never receives streamed buckets — IssuesClient only streams for
        # Excel/CSV. Guard anyway so a future change cannot drop them silently.
        if streamed_csvs:
            log.warning(
                "%d streamed bucket(s) cannot be rendered to Word; "
                "generating Excel instead so no issues are lost.",
                len(streamed_csvs),
            )
            return ExcelReport(self.output_dir, self.project_key, "excel", self.verbosity).generate(
                issues, qg, streamed_csvs, cleanup_temp=cleanup
            )

        return WordReport(*args).generate(metrics, qg, issues)


# loominar/report/report_manager.py
# A clean orchestrator to pick the correct report generator dynamically
