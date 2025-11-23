import sys
from loominar.cli_handler import get_cli_inputs
from loominar.input_handler import get_user_inputs
from loominar.api import MetricsClient, IssuesClient
from loominar.report.report_manager import ReportManager
from loominar import __version__
from loominar import console as c


def main():
    c.info(f"\n🧶 Loominar v{__version__} — SonarQube Report Exporter\n", bold=True)

    try:
        # Step 1: Parse CLI inputs (non-interactive mode)
        cli_cfg = get_cli_inputs()

        # Step 2: Collect user inputs (fills missing fields using cli defaults)
        cfg = get_user_inputs(cli_defaults=cli_cfg)

        # Step 3: Initialize API clients (verbosity controlled by cfg)
        metrics_api = MetricsClient(cfg["sonar_url"], cfg["sonar_token"], verbosity=cfg["verbosity"])
        issues_api = IssuesClient(cfg["sonar_url"], cfg["sonar_token"], verbosity=cfg["verbosity"])

        # Step 4: Fetch data
        #Introduced new variable setdefault for 10k confirmation
        c.info("📡 Fetching SonarQube data...", bold=True)
        metrics = metrics_api.get_metrics(cfg["project_key"])
        qg = metrics_api.get_quality_gate(cfg["project_key"])

        # Pass output_dir to get_all_issues and capture streamed CSVs
        issues, fmt, large_warn, streamed_csvs = issues_api.get_all_issues(
            cfg["project_key"], cfg["format"], cfg["no_confirm"], cfg["output_dir"], cfg.get("large_warn", False)
        )
        cfg["large_warn"] = large_warn

        if not cfg.get("no_confirm") and not cfg.get("large_warn"):
            c.prompt(f"\nProceed to generate {fmt.upper()} report? (Y/n): ", bold=True)
            confirm = input().strip().lower()
            if confirm == "n":
                c.warn("❌ Operation cancelled by user.")
                sys.exit(0)

        # Step 6: Generate report
        c.info(f"\n🧾 Generating {fmt.upper()} report...", bold=True)
        report = ReportManager(cfg["output_dir"], cfg["project_key"], fmt)
        report.generate(metrics, qg, issues, streamed_csvs)

        c.success(f"\n✅ Report successfully saved to: {cfg['output_dir']}")

    except KeyboardInterrupt:
        c.error("\n❌ Operation cancelled by user (KeyboardInterrupt).")
        sys.exit(1)

    except Exception as e:
        # print a concise error with color; include exception type for debugging
        c.error(f"\n💥 Error: {type(e).__name__}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


"""
Entry point for Loominar CLI / interactive tool.

Features:
- Supports both CLI and interactive mode (cli_handler + input_handler).
- Uses loominar.console for colorized, PowerShell-safe output.
- Respects --no-confirm for automation.
- Clean error handling with proper exit codes for CI consumption.
"""
