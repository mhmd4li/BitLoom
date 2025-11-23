from datetime import datetime, timedelta
from typing import List, Tuple

def monthly_windows(now: datetime = None, months: int = 12) -> List[Tuple[str, str]]:
    now = now or datetime.utcnow()
    windows = []
    for m in range(months):
        end = now - timedelta(days=m * 30)
        start = end - timedelta(days=30)
        windows.append((start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")))
    return windows

def iso_midpoint(start_iso: str, end_iso: str) -> str:
    s = datetime.fromisoformat(start_iso)
    e = datetime.fromisoformat(end_iso)
    mid = s + (e - s) / 2
    return mid.isoformat(timespec="seconds")

# Return a list of (start_iso, end_iso) windows for the past `months` months.
