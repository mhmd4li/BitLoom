from loominar import console

from .base_client import BaseClient

log = console.get_logger(__name__)

METRIC_KEYS = "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"


class MetricsClient(BaseClient):
    def get_metrics(self, project_key):
        data = self.get("/api/measures/component", {"component": project_key, "metricKeys": METRIC_KEYS})
        # A missing project returns a body without "component"; a bare KeyError
        # here told the user nothing about what went wrong.
        component = (data or {}).get("component")
        if not component:
            log.warning("No measures returned for project '%s'; metrics will be omitted.", project_key)
            return []
        measures = component.get("measures", [])
        log.debug("Read %d measures for project '%s'", len(measures), project_key)
        return measures

    def get_quality_gate(self, project_key):
        data = self.get("/api/qualitygates/project_status", {"projectKey": project_key})
        status = (data or {}).get("projectStatus")
        if not status:
            log.warning("No quality gate configured for project '%s'.", project_key)
            return {}
        log.debug("Quality gate for '%s': %s", project_key, status.get("status", "unknown"))
        return status


# loominar/api/metrics_client.py
# Metrics and quality gate
# High-Level Metrics + Quality Gate
# Simple, compact, and clean
