import re
import time

import requests
from requests import ConnectionError, HTTPError, RequestException, Timeout

from loominar import console

log = console.get_logger(__name__)

RETRY_COUNT = 3
RETRY_BACKOFF = 1.0  # base seconds
REQUEST_TIMEOUT = 30

# 4xx is a client mistake and retrying will not help - except for these two,
# which mean "you are going too fast" / "come back shortly".
RETRYABLE_STATUSES = {408, 429}

_SENSITIVE_KEYS = {"token", "password", "secret", "authorization", "login"}


def _loggable(params):
    """Redact anything credential-shaped before it reaches a CI log."""
    if not params:
        return {}
    return {
        k: ("***" if k.lower() in _SENSITIVE_KEYS else v)
        for k, v in params.items()
    }


# requests wraps urllib3 which wraps the OS error, so str(exc) is three layers of
# boilerplate around one useful sentence. These pull that sentence back out.
_CAUSED_BY = re.compile(r"Caused by \w+\(['\"](.*)['\"]\)\s*\)?\s*$", re.DOTALL)
_OBJECT_REPR = re.compile(r"<[^>]*object at 0x[0-9a-fA-F]+>:\s*")
_POOL_PREFIX = re.compile(r"^HTTP[S]?ConnectionPool\([^)]*\):\s*")


def brief_error(exc, limit=300):
    """Condense a requests/urllib3 exception chain into one readable clause."""
    text = str(exc).strip()
    match = _CAUSED_BY.search(text)
    if match:
        text = match.group(1)
    text = _OBJECT_REPR.sub("", text)
    text = _POOL_PREFIX.sub("", text)
    text = " ".join(text.split())
    return text[:limit] if len(text) > limit else text


class BaseClient:
    def __init__(self, base_url, token, verbosity=None):
        self.base_url = (base_url or "").rstrip("/")
        # Verbosity is global logger state; honour it here so library callers
        # who never invoke console.configure() still get the level they asked for.
        if verbosity is not None:
            console.set_verbosity(verbosity)
        # A pooled session reuses the TCP/TLS connection. A large export makes
        # thousands of requests; a fresh handshake for each one dominates runtime.
        self.session = requests.Session()
        self.session.auth = (token, "")
        self.session.headers.update({"Accept": "application/json"})

    def _sleep_for(self, attempt, response=None):
        """Exponential backoff, but honour Retry-After when the server sends it."""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(float(retry_after), 60.0)
                except ValueError:
                    pass
        return RETRY_BACKOFF * (2 ** (attempt - 1))

    def get(self, endpoint, params=None):
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        url = f"{self.base_url}{endpoint}"

        last_exc = None
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                log.debug("GET %s params=%s", endpoint, _loggable(params))

                started = time.monotonic()
                resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                elapsed = time.monotonic() - started

                log.debug(
                    "GET %s -> HTTP %s (%d bytes) in %.0fms",
                    endpoint, resp.status_code, len(resp.content), elapsed * 1000,
                )

                if 400 <= resp.status_code < 500 and resp.status_code not in RETRYABLE_STATUSES:
                    body = (resp.text or "")[:500]
                    log.debug("HTTP %s body: %s", resp.status_code, body)
                    raise RuntimeError(f"HTTP {resp.status_code} for {endpoint}: {body}")

                resp.raise_for_status()

                try:
                    return resp.json()
                except ValueError:
                    log.warning(
                        "Response from %s was not valid JSON (HTTP %s); treating it as empty.",
                        endpoint, resp.status_code,
                    )
                    return {}

            except (HTTPError, Timeout, ConnectionError, RequestException) as exc:
                last_exc = exc
                response = getattr(exc, "response", None)

                reason = brief_error(exc)

                if attempt == RETRY_COUNT:
                    snippet = ""
                    try:
                        snippet = (getattr(response, "text", "") or "")[:200].strip()
                    except Exception:
                        snippet = ""
                    # Raise only; the caller decides whether this is fatal and
                    # logs it once. Logging here too would triple the noise.
                    detail = f" Server said: {snippet}" if snippet else ""
                    raise RuntimeError(
                        f"{endpoint} failed after {RETRY_COUNT} attempts: {reason}.{detail}"
                    ) from exc

                sleep_for = self._sleep_for(attempt, response)
                log.warning(
                    "%s failed (attempt %d/%d): %s. Retrying in %.1fs.",
                    endpoint, attempt, RETRY_COUNT, reason, sleep_for,
                )
                time.sleep(sleep_for)

        raise RuntimeError(f"Failed to GET {endpoint}: {last_exc}")

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


# Core request/response handling + retries
# Low-level HTTP Engine
# Handles all authenticated requests, retry logic, and debug verbosity
