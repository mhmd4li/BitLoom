from pathlib import Path
from typing import List, Dict, Any, Iterable
from loominar.api.issues.excel_stream import merge_csvs_and_issues_to_xlsx as api_merge
# Reuse the API helper for the actual merge; this keeps logic DRY

def merge_streamed_csvs_and_issues(output_path: Path, csv_paths: List[str], issues_in_memory: Iterable[Dict[str, Any]] = None) -> Path:
    return api_merge(output_path, csv_paths, issues_in_memory)
