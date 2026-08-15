import sys

from loominar import __version__
from loominar import console
from loominar.api import IssuesClient, MetricsClient
from loominar.api.issues.pagination import ProbeError
from loominar.cli_handler import get_cli_inputs
from loominar.input_handler import MissingInputError, get_user_inputs
from loominar.report.report_manager import ReportManager

log = console.get_logger(__name__)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CANCELLED = 2
EXIT_BAD_INPUT = 3


def _confirm(question: str) -> bool:
    """Anything other than an explicit yes cancels - 'q', 'no', or a stray
    keypress used to be read as approval."""
    console.prompt(question)
    try:
        answer = input().strip().lower()
    except EOFError:
        return False
    return answer in ("", "y", "yes")


def main():
    cli_cfg = {}
    try:
        cli_cfg = get_cli_inputs()
        console.configure(
            verbosity=cli_cfg.get("verbosity", 2),
            color=cli_cfg.get("color"),
            timestamps=cli_cfg.get("timestamps"),
        )

        console.banner(f"Loominar v{__version__} - SonarQube Report Exporter")

        cfg = get_user_inputs(cli_defaults=cli_cfg)
        log.debug(
            "Configuration: url=%s project=%s format=%s output=%s inline_limit=%s headless=%s",
            cfg["sonar_url"], cfg["project_key"], cfg["format"],
            cfg["output_dir"], cfg["inline_limit"], cfg["headless"],
        )

        metrics_api = MetricsClient(cfg["sonar_url"], cfg["sonar_token"])
        issues_api = IssuesClient(cfg["sonar_url"], cfg["sonar_token"])

        log.info("Connecting to %s", cfg["sonar_url"])

        # Metrics and the quality gate are decorative; a project without them
        # should still produce an issue report.
        try:
            metrics = metrics_api.get_metrics(cfg["project_key"])
        except Exception as exc:
            log.warning("Could not read project metrics: %s", exc)
            metrics = []

        try:
            qg = metrics_api.get_quality_gate(cfg["project_key"])
        except Exception as exc:
            log.warning("Could not read quality gate: %s", exc)
            qg = {}

        try:
            issues, fmt, large_warn, streamed_csvs = issues_api.get_all_issues(
                cfg["project_key"],
                cfg["format"],
                cfg["no_confirm"],
                cfg["output_dir"],
                cfg.get("large_warn", False),
                split_dims=cfg.get("split_by"),
                inline_limit=cfg.get("inline_limit", 10000),
            )
        except ProbeError as exc:
            # Distinct from "the project has no issues" - do not exit 0 here, or
            # a pipeline will read an unreachable server as a clean run.
            log.error(
                "Could not read the issue count for '%s' from %s.\n"
                "Check the URL, token, and project key. Cause: %s",
                cfg["project_key"], cfg["sonar_url"], exc,
            )
            return EXIT_ERROR
        cfg["large_warn"] = large_warn

        if not issues and not streamed_csvs:
            log.warning("Nothing to report: no open issues were retrieved.")
            return EXIT_OK

        # `large_warn` means the user was already asked about this run; don't
        # make them confirm twice.
        if not cfg["no_confirm"] and not large_warn and not cfg["headless"]:
            if not _confirm(f"Generate the {fmt.upper()} report now? (Y/n): "):
                log.warning("Cancelled by user; no report was written.")
                return EXIT_CANCELLED

        log.info("Generating %s report in %s", fmt.upper(), cfg["output_dir"])
        report = ReportManager(
            cfg["output_dir"], cfg["project_key"], fmt, cfg["verbosity"], cfg.get("keep_temp", False)
        )
        path = report.generate(metrics, qg, issues, streamed_csvs)

        if not path:
            log.error("Report generation produced no file.")
            return EXIT_ERROR

        # The report path is the run's result: stdout, so a pipeline can capture it.
        console.result(path)
        return EXIT_OK

    except MissingInputError as exc:
        log.error("%s", exc)
        return EXIT_BAD_INPUT

    except KeyboardInterrupt:
        log.error("Interrupted; no report was written.")
        return EXIT_CANCELLED

    except Exception as exc:
        # The traceback is the first thing anyone debugging a pipeline wants,
        # but it is noise at normal verbosity.
        log.error("%s: %s", type(exc).__name__, exc, exc_info=console.is_debug())
        if not console.is_debug():
            log.error("Re-run with -v 3 for the full traceback.")
        return EXIT_ERROR


def run():
    """Console-script entry point: translate the return value into an exit code."""
    sys.exit(main())


if __name__ == "__main__":
    run()


"""
Entry point for Loominar CLI / interactive tool.

Features:
- Supports both CLI and interactive mode (cli_handler + input_handler).
- Diagnostics go to stderr; the finished report path goes to stdout.
- Respects --no-confirm for automation.
- Clean error handling with proper exit codes for CI consumption:
  0 success, 1 error, 2 cancelled, 3 bad/missing input.
"""
