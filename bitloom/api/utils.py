import sys

def render_progress(current, total, prefix="", bar_length=40):
    total = max(total, 1)
    filled = int(bar_length * current // total)
    bar = "█" * filled + "-" * (bar_length - filled)
    percent = (current / total) * 100
    sys.stdout.write(f"\r{prefix} [{bar}] {percent:5.1f}%")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


## bitloom/api/utils.py
# Common functions like progress bar + verbosity logger
# Keeps UI/verbosity helper logic cleanly isolated
