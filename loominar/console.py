from colorama import init as colorama_init, Fore, Style

# Initialize colorama (handles colors on Windows PowerShell / CMD)
# autoreset keeps us from having to manually reset styles after every print
colorama_init(autoreset=True)

# Styles
_BOLD = Style.BRIGHT
_RESET = Style.RESET_ALL

def success(msg: str, *, bold: bool = True) -> None:
    """Green positive message."""
    prefix = _BOLD if bold else ""
    print(f"{prefix}{Fore.GREEN}{msg}{_RESET}")

def error(msg: str, *, bold: bool = True, flush: bool = False) -> None:
    """Red error message."""
    prefix = _BOLD if bold else ""
    print(f"{prefix}{Fore.RED}{msg}{_RESET}", flush=flush)

def info(msg: str, *, bold: bool = False, flush: bool = False) -> None:
    """Cyan informational message (for status)."""
    prefix = _BOLD if bold else ""
    print(f"{prefix}{Fore.CYAN}{msg}{_RESET}", flush=flush)

def warn(msg: str, *, bold: bool = False, flush: bool = False) -> None:
    """Yellow-ish warning (falls back to bright yellow)."""
    prefix = _BOLD if bold else ""
    print(f"{prefix}{Fore.YELLOW}{msg}{_RESET}", flush=flush)

def prompt(msg: str, *, bold: bool = False) -> None:
    """Cyan prompt (non-blocking print) — still use input() for reading."""
    prefix = _BOLD if bold else ""
    print(f"{prefix}{Fore.CYAN}{msg}{_RESET}", end="")
