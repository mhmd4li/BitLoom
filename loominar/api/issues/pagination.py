from typing import Iterator, Dict, Any

PAGE_SIZE_DEFAULT = 500

def fetch_all_pages(client, endpoint: str, base_params: Dict[str, Any], page_size: int = PAGE_SIZE_DEFAULT) -> Iterator[Dict[str, Any]]:
    params = base_params.copy()
    params["ps"] = page_size
    params["p"] = 1

    first = client.get(endpoint, params)
    if not first:
        return

    for issue in first.get("issues", []) or []:
        yield issue

    paging = first.get("paging", {}) or {}
    total_pages = paging.get("pages", 1)

    for p in range(2, total_pages + 1):
        params["p"] = p
        data = client.get(endpoint, params)
        for issue in (data.get("issues", []) or []):
            yield issue


# Yield items (issue dicts) across all pages using the server-provided paging.pages.
