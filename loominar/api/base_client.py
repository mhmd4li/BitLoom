import requests
import sys
import time
from loominar import console as c
from requests import RequestException, HTTPError, Timeout, ConnectionError

RETRY_COUNT = 3
RETRY_BACKOFF = 1.0  # base seconds

class BaseClient:
    def __init__(self, base_url, token, verbosity=2):
        self.base_url = base_url.rstrip("/")
        self.auth = (token, "")
        self.verbosity = verbosity

    def _log(self, message, level=2, severity=1):
        if self.verbosity >= level:
            if severity == 1:
                c.info(message, flush=True)
            elif severity == 2:
                c.warn(message, flush=True)
            elif severity == 3:
                c.error(message, flush=True)

    def get(self, endpoint, params=None):

        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        url = f"{self.base_url}{endpoint}"

        last_exc = None
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                if self.verbosity >= 3:
                    c.info(f"[DEBUG] GET {url} params={params}")
                resp = requests.get(url, params=params, auth=self.auth, timeout=15)

                if self.verbosity >= 3:
                    c.info(f"[DEBUG] → {resp.status_code}, {len(resp.text)} bytes")

                # If status code indicates client error (4xx), capture body and raise immediately
                if 400 <= resp.status_code < 500:
                    body = resp.text or ""
                    # show a short snippet for debugging
                    if self.verbosity >= 2:
                        c.info(f"[DEBUG] 4xx response body (snippet): {body[:500]}")
                    raise RuntimeError(f"HTTP {resp.status_code} for {endpoint}: {body}")

                # For other status codes, let requests raise if not OK (this will take care of 5xx)
                resp.raise_for_status()

                # Try to parse JSON, but return empty dict on parse error
                try:
                    return resp.json()
                except ValueError:
                    return {}

            except (HTTPError, Timeout, ConnectionError, RequestException) as exc:
                last_exc = exc
                # If it's an HTTPError raised by raise_for_status() and status was 4xx,
                # the case is already handled above. Here we handle transient/network/server errors.
                self._log(f"⚠️ Attempt {attempt} failed: {exc}", 1, 2)

                # If this was the last attempt, raise a runtime error including the last response text
                if attempt == RETRY_COUNT:
                    # Try to include response text if present on exception
                    resp_text = ""
                    try:
                        resp_text = getattr(exc.response, "text", "") or ""
                    except Exception:
                        resp_text = ""
                    raise RuntimeError(f"Failed after {RETRY_COUNT} attempts for {endpoint}: {str(exc)}. Server response snippet: {resp_text[:1000]}") from exc

                # exponential backoff before retrying
                sleep_for = RETRY_BACKOFF * (2 ** (attempt - 1))
                if self.verbosity >= 3:
                    c.info(f"[DEBUG] Sleeping {sleep_for}s before retry")
                time.sleep(sleep_for)

        # If we somehow fell out of loop, raise with last exception
        raise RuntimeError(f"Failed to GET {endpoint}: {last_exc}")


# Core request/response handling + retries
# Low-level HTTP Engine
# Handles all authenticated requests, retry logic, and debug verbosity