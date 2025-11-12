import argparse

def get_cli_inputs():
    parser = argparse.ArgumentParser(
        prog="loominar",
        description="🧶 Loominar — SonarQube Report Exporter\n"
                    "Export SonarQube quality metrics into professional Word, Excel, or CSV reports.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("-u", "--url", help="SonarQube server URL (e.g., http://localhost:9000)")
    parser.add_argument("-t", "--token", help="SonarQube API token")
    parser.add_argument("-p", "--project", help="SonarQube project key")
    parser.add_argument("-f", "--format", choices=["word", "excel", "csv"], help="Output format")
    parser.add_argument("-o", "--output", help="Output directory (default: Documents/Loominar)")
    parser.add_argument("-v", "--verbosity", type=int, choices=[1, 2, 3], default=2, help="Verbosity level (1–3)")
    parser.add_argument("--no-confirm", action="store_true", help="Skip confirmation prompts for automation")

    args = parser.parse_args()

    # Convert argparse Namespace → dict
    cli_cfg = {k: v for k, v in vars(args).items() if v is not None}
    return cli_cfg
