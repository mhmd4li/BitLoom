"""
Structured, colorized logging for Loominar.

Diagnostics go to **stderr** and the finished report path goes to **stdout**, so
a pipeline can do `REPORT=$(loominar ... --no-confirm)` without having to strip
progress chatter out of the result.

Verbosity maps onto standard logging levels:

    -v 1  quiet    success + warnings + errors
    -v 2  normal   adds progress and status  (default)
    -v 3  debug    adds HTTP traffic, paging, and timings

Color is dropped automatically when stderr is not a terminal, when ``NO_COLOR``
is set, or when ``TERM=dumb`` — so CI logs stay free of escape sequences.
"""

import logging
import os
import sys
import time

from colorama import Fore, Style
from colorama import init as colorama_init

LOGGER_NAME = "loominar"

# Sits between INFO and WARNING: visible in quiet mode, but not an alarm.
SUCCESS = 25
logging.addLevelName(SUCCESS, "OK")

VERBOSITY_LEVELS = {1: SUCCESS, 2: logging.INFO, 3: logging.DEBUG}

_LEVEL_TAGS = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    SUCCESS: "OK",
    logging.WARNING: "WARN",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "FATAL",
}

_LEVEL_COLORS = {
    logging.DEBUG: Style.DIM,
    logging.INFO: Fore.CYAN,
    SUCCESS: Style.BRIGHT + Fore.GREEN,
    logging.WARNING: Fore.YELLOW,
    logging.ERROR: Style.BRIGHT + Fore.RED,
    logging.CRITICAL: Style.BRIGHT + Fore.RED,
}

_TAG_WIDTH = max(len(t) for t in _LEVEL_TAGS.values())


class LoominarLogger(logging.Logger):
    """Adds the SUCCESS level so completion messages survive quiet mode."""

    def success(self, msg, *args, **kwargs):
        if self.isEnabledFor(SUCCESS):
            self._log(SUCCESS, msg, args, **kwargs)


# Must precede the first getLogger call so every Loominar logger gets .success().
logging.setLoggerClass(LoominarLogger)

_root = logging.getLogger(LOGGER_NAME)
_root.propagate = False

_handler = None
_color_enabled = False


class _Formatter(logging.Formatter):
    """`[LEVEL] message`, optionally timestamped, with wrapped lines aligned."""

    def __init__(self, color=True, timestamps=False):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.color = color
        self.timestamps = timestamps

    def format(self, record):
        tag = _LEVEL_TAGS.get(record.levelno, record.levelname)
        plain_prefix = f"[{tag:<{_TAG_WIDTH}}] "
        if self.timestamps:
            plain_prefix = f"{self.formatTime(record, self.datefmt)} {plain_prefix}"

        if self.color:
            color = _LEVEL_COLORS.get(record.levelno, "")
            prefix = f"{color}{plain_prefix}{Style.RESET_ALL}"
        else:
            prefix = plain_prefix

        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"

        # Align continuation lines under the message, not under the tag, so
        # multi-line detail stays readable in a wall of CI output.
        lines = message.split("\n")
        pad = " " * len(plain_prefix)
        body = f"\n{pad}".join(lines)
        return f"{prefix}{body}"


def _is_tty(stream):
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def _should_color(stream, override=None):
    if override is not None:
        return bool(override)
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return _is_tty(stream)


def configure(verbosity=2, stream=None, color=None, timestamps=None):
    """
    Install Loominar's log handler. Safe to call more than once.

    `timestamps` defaults to on whenever stderr is redirected — a CI log or a
    file wants them, an attached terminal does not.
    """
    global _handler, _color_enabled

    colorama_init()
    stream = stream if stream is not None else sys.stderr

    if timestamps is None:
        timestamps = not _is_tty(stream)

    _color_enabled = _should_color(stream, color)

    if _handler is not None:
        _root.removeHandler(_handler)

    _handler = logging.StreamHandler(stream)
    _handler.setFormatter(_Formatter(color=_color_enabled, timestamps=timestamps))
    _root.addHandler(_handler)
    set_verbosity(verbosity)
    return _root


def set_verbosity(verbosity):
    _root.setLevel(VERBOSITY_LEVELS.get(int(verbosity or 2), logging.INFO))


def get_logger(name=None):
    """Logger for a module: `get_logger(__name__)`."""
    if not name or name == LOGGER_NAME:
        return _root
    short = name.split(".")[-1] if name.startswith(LOGGER_NAME) else name
    return _root.getChild(short)


def is_debug():
    return _root.isEnabledFor(logging.DEBUG)


# --- direct-to-terminal output -------------------------------------------------

def banner(text):
    """Program header — stderr, so it never pollutes captured stdout."""
    stream = sys.stderr
    if _should_color(stream, None):
        stream.write(f"{Style.BRIGHT}{Fore.CYAN}{text}{Style.RESET_ALL}\n")
    else:
        stream.write(f"{text}\n")
    stream.flush()


def prompt(message):
    """Question for the user. Not a log record — no level tag, no newline."""
    stream = sys.stderr
    if _should_color(stream, None):
        stream.write(f"{Style.BRIGHT}{Fore.CYAN}{message}{Style.RESET_ALL}")
    else:
        stream.write(message)
    stream.flush()


def result(text):
    """The one thing a pipeline wants to capture: print it on stdout."""
    sys.stdout.write(f"{text}\n")
    sys.stdout.flush()


# --- progress ------------------------------------------------------------------

class ProgressReporter:
    """
    Time-throttled progress logging.

    Throttling on elapsed time rather than row count keeps output steady whether
    the server answers in 20ms or two seconds, and stops a long export from
    burying its own warnings under thousands of progress lines.
    """

    def __init__(self, label, total=None, logger=None, interval=5.0, level=logging.INFO):
        self.label = label
        self.total = total or 0
        self.log = logger or _root
        self.interval = interval
        self.level = level
        self.count = 0
        self._started = time.monotonic()
        self._last = self._started

    def advance(self, n=1):
        self.count += n
        now = time.monotonic()
        if now - self._last >= self.interval:
            self._last = now
            self.log.log(self.level, "%s: %s", self.label, self._describe(now))

    def done(self, level=None):
        elapsed = time.monotonic() - self._started
        self.log.log(
            self.level if level is None else level,
            "%s: %s",
            self.label,
            self._describe(time.monotonic(), final=True),
        )
        return elapsed

    def _describe(self, now, final=False):
        elapsed = max(now - self._started, 1e-6)
        rate = self.count / elapsed
        if self.total:
            pct = min(100.0, self.count * 100.0 / self.total)
            head = f"{self.count:,}/{self.total:,} ({pct:.0f}%)"
        else:
            head = f"{self.count:,} issues"
        tail = f"{rate:,.0f}/s"
        if final:
            tail = f"{tail}, {elapsed:.1f}s total"
        return f"{head} at {tail}"


# Configure a sane default so importing the package and logging immediately
# works even if main() has not run (library use, tests).
configure()
