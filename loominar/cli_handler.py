import argparse
import os

from loominar import __version__

# Reading credentials from the environment keeps the token out of argv, where
# it would otherwise show up in process listings and CI job logs.
ENV_DEFAULTS = {
    "url": "SONAR_URL",
    "token": "SONAR_TOKEN",
    "project": "SONAR_PROJECT",
}


def get_cli_inputs(argv=None):
    parser = argparse.ArgumentParser(
        prog="loominar",
        description="Loominar - SonarQube Report Exporter. "
                    "Export SonarQube quality metrics into Word, Excel, or CSV reports.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Credentials can also be supplied via SONAR_URL, SONAR_TOKEN and SONAR_PROJECT, "
               "which is preferred in pipelines: a token passed as --token is visible in "
               "process listings and CI logs. Log output goes to stderr and the finished "
               "report path goes to stdout, so REPORT=$(loominar ... --no-confirm) works.",
    )

    parser.add_argument("-u", "--url", help="SonarQube server URL (e.g., http://localhost:9000) [env: SONAR_URL]")
    parser.add_argument("-t", "--token", help="SonarQube API token [env: SONAR_TOKEN]")
    parser.add_argument("-p", "--project", help="SonarQube project key [env: SONAR_PROJECT]")
    parser.add_argument("-f", "--format", choices=["word", "excel", "csv"], help="Output format")
    parser.add_argument("-o", "--output", help="Output directory (default: Documents/Loominar)")
    parser.add_argument(
        "-v", "--verbosity", type=int, choices=[1, 2, 3], default=2,
        help="1 = warnings and results only, 2 = progress, 3 = debug (HTTP, paging, timings)",
    )
    # SUPPRESS keeps these aliases from advertising a competing default; the
    # namespace value still comes from -v, which is added first.
    parser.add_argument(
        "-q", "--quiet", action="store_const", const=1, dest="verbosity",
        default=argparse.SUPPRESS, help="Shorthand for -v 1",
    )
    parser.add_argument(
        "--debug", action="store_const", const=3, dest="verbosity",
        default=argparse.SUPPRESS, help="Shorthand for -v 3",
    )
    parser.add_argument(
        "--color", action=argparse.BooleanOptionalAction, default=None,
        help="Force color on or off (default: on when stderr is a terminal; NO_COLOR is honoured)",
    )
    parser.add_argument(
        "--timestamps", action=argparse.BooleanOptionalAction, default=None,
        help="Prefix log lines with a timestamp (default: on when stderr is redirected)",
    )
    parser.add_argument(
        "--inline-limit",
        type=int,
        default=10000,
        help="Above this issue count, buckets are streamed to disk and the report falls back to Excel",
    )
    parser.add_argument(
        "--split-by",
        default="severity,type,date",
        help="Comma-separated split dimensions for large projects (severity, type, component, date)",
    )
    parser.add_argument("--no-confirm", action="store_true", help="Skip confirmation prompts for automation")
    parser.add_argument("--keep-temp", action="store_true", help="Keep the intermediate .loominar_temp CSVs")
    parser.add_argument("--version", action="version", version=f"loominar {__version__}")

    args = parser.parse_args(argv)

    # Drop unset values so interactive prompts and env defaults can fill them in.
    cli_cfg = {k: v for k, v in vars(args).items() if v is not None}

    for key, env_var in ENV_DEFAULTS.items():
        if not cli_cfg.get(key):
            env_value = os.environ.get(env_var)
            if env_value:
                cli_cfg[key] = env_value

    cli_cfg["split_by"] = [d.strip() for d in str(cli_cfg.get("split_by", "")).split(",") if d.strip()]
    return cli_cfg
