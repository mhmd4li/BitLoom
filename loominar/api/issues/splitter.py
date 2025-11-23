# loominar/api/issues/splitter.py
from typing import Iterator, Tuple, Dict, Any, List
from .components import list_components
from .date_utils import monthly_windows, iso_midpoint

MAX_RESULTS = 10000
TYPES = ["BUG", "VULNERABILITY", "CODE_SMELL"]

def iter_split_filters(client, project_key: str, base_filters: Dict[str, Any], split_dims: List[str] = None) -> Iterator[Tuple[Dict[str, Any], int]]:

    if split_dims is None:
        split_dims = ["type", "component", "date"]

    # Probe
    try:
        probe = client.get("/api/issues/search", {**base_filters, "ps": 1, "p": 1})
    except Exception:
        return

    total = probe.get("paging", {}).get("total", 0)
    if total <= MAX_RESULTS or not split_dims:
        yield base_filters, total
        return

    dim = split_dims[0]

    if dim == "type":
        for t in TYPES:
            filters = {**base_filters, "types": t}
            yield from iter_split_filters(client, project_key, filters, split_dims[1:])
        return

    if dim == "component":
        components = list_components(client, project_key)
        if not components:
            yield from iter_split_filters(client, project_key, base_filters, split_dims[1:])
            return
        for comp in components:
            filters = {**base_filters, "componentKeys": comp}
            yield from iter_split_filters(client, project_key, filters, split_dims[1:])
        return

    if dim == "date":
        for start_iso, end_iso in monthly_windows():
            date_filters = {**base_filters, "createdAfter": start_iso, "createdBefore": end_iso}
            try:
                probe = client.get("/api/issues/search", {**date_filters, "ps": 1, "p": 1})
                sub_total = probe.get("paging", {}).get("total", 0)
            except Exception:
                sub_total = 0
            if sub_total == 0:
                continue
            if sub_total <= MAX_RESULTS:
                yield date_filters, sub_total
            else:
                # binary split
                mid = iso_midpoint(start_iso, end_iso)
                first_half = {**base_filters, "createdAfter": start_iso, "createdBefore": mid}
                second_half = {**base_filters, "createdAfter": mid, "createdBefore": end_iso}
                yield from iter_split_filters(client, project_key, first_half, split_dims[1:])
                yield from iter_split_filters(client, project_key, second_half, split_dims[1:])
        # fallback: if windows are not suitable
        yield base_filters, total
        return

    # fallback
    yield base_filters, total


# Yield (filters, total) pairs. Recursively split filters until each bucket <= MAX_RESULTS.
# Splitting order (default): type -> component -> date