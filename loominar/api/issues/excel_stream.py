from pathlib import Path
import csv
import xlsxwriter
from typing import List, Dict, Any, Iterable

def _safe_sheet_name(name: str) -> str:
    s = name.replace("/", "_").replace("\\", "_")[:31]
    return s

def csv_to_sheet(workbook: xlsxwriter.Workbook, sheet_name: str, csv_path: Path):
    ws = workbook.add_worksheet(_safe_sheet_name(sheet_name))
    with csv_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for r_idx, row in enumerate(reader):
            ws.write_row(r_idx, 0, row)

def issues_to_sheet(workbook: xlsxwriter.Workbook, sheet_name: str, issues: Iterable[Dict[str, Any]]):
    issues = list(issues)
    if not issues:
        return
    ws = workbook.add_worksheet(_safe_sheet_name(sheet_name))
    headers = list(issues[0].keys())
    ws.write_row(0, 0, headers)
    for r_idx, issue in enumerate(issues, start=1):
        row = [issue.get(h, "") for h in headers]
        ws.write_row(r_idx, 0, row)

def merge_csvs_and_issues_to_xlsx(output_path: Path, csv_paths: List[str], issues_in_memory: Iterable[Dict[str, Any]] = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(output_path), {'constant_memory': True})
    try:
        for csv_path in csv_paths or []:
            path = Path(csv_path)
            sheet_name = path.stem
            csv_to_sheet(workbook, sheet_name, path)
        if issues_in_memory:
            issues_to_sheet(workbook, "in_memory_issues", issues_in_memory)
    finally:
        workbook.close()
    return output_path
