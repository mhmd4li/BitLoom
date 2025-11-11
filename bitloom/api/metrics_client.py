from .base_client import BaseClient

class MetricsClient(BaseClient):
    def get_metrics(self, project_key):
        data = self.get(
            "/api/measures/component",
            {
                "component": project_key,
                "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"
            }
        )
        return data["component"]["measures"]

    def get_quality_gate(self, project_key):
        data = self.get("/api/qualitygates/project_status", {"projectKey": project_key})
        return data["projectStatus"]

# bitloom/api/metrics_client.py
# Metrics and quality gate
# High-Level Metrics + Quality Gate
# Simple, compact, and clean