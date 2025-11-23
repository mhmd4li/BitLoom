from pathlib import Path
import csv
from typing import List, Dict, Any, Optional
from .pagination import fetch_all_pages

def stream_filters_to_csv(client, project_key: str, filters: Dict[str, Any], out_dir: Path, page_size: int = 500) -> Optional[str]:

    temp_dir = Path(out_dir) / ".loominar_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    sev = filters.get("severities", "all")
    typ = filters.get("types", "all")
    safe_name = f"{project_key}_{sev}_{typ}".replace(" ", "_")
    out_path = temp_dir / f"{safe_name}.csv"
    first_write = not out_path.exists()

    try:
        with out_path.open("a", newline="", encoding="utf-8") as fh:
            writer = None
            for issue in fetch_all_pages(client, "/api/issues/search", filters, page_size=page_size):
                if writer is None:
                    fieldnames = list(issue.keys())
                    writer = csv.DictWriter(fh, fieldnames=fieldnames)
                    if first_write:
                        writer.writeheader()
                        first_write = False
                writer.writerow(issue)
    except Exception:
        return None
    return str(out_path)

# Stream issues matching `filters` to a CSV file under out_dir/.loominar_temp/.
# Returns path to CSV or None on error.

