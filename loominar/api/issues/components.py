from typing import List

def list_components(client, project_key: str) -> List[str]:
    try:
        resp = client.get("/api/components/search", {"project": project_key, "ps": 500})
        comps = resp.get("components", []) or []
        return [c.get("key") for c in comps if c.get("key")]
    except Exception:
        return []

# Return component keys for a project. Returns empty list on error.