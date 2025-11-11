from bitloom.input_handler import get_user_inputs
from bitloom.api import MetricsClient, IssuesClient
from bitloom.report.report_manager import ReportManager

def main():
    cfg = get_user_inputs()

    metrics_api = MetricsClient(cfg["sonar_url"], cfg["sonar_token"], verbosity=cfg["verbosity"])
    issues_api = IssuesClient(cfg["sonar_url"], cfg["sonar_token"], verbosity=cfg["verbosity"])

    metrics = metrics_api.get_metrics(cfg["project_key"])
    qg = metrics_api.get_quality_gate(cfg["project_key"])
    issues, fmt = issues_api.get_all_issues(cfg["project_key"], cfg["format"])

    report = ReportManager(cfg["output_dir"], cfg["project_key"], fmt)
    report.generate(metrics, qg, issues)

if __name__ == "__main__":
    main()
