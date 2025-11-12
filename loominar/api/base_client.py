import requests
import sys
import time
import console as c

class BaseClient:
    def __init__(self, base_url, token, verbosity=2):
        self.base_url = base_url.rstrip("/")
        self.auth = (token, "")
        self.verbosity = verbosity

    def _log(self, message, level=2):
        if self.verbosity >= level:
            c.info(message, flush=True)

    def get(self, endpoint, params=None):
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        url = f"{self.base_url}{endpoint}"

        for attempt in range(3):
            try:
                if self.verbosity >= 3:
                    c.info(f"[DEBUG] GET {url} params={params}")
                resp = requests.get(url, params=params, auth=self.auth, timeout=15)
                if self.verbosity >= 3:
                    c.info(f"[DEBUG] → {resp.status_code}, {len(resp.text)} bytes")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                self._log(f"⚠️ Attempt {attempt + 1} failed: {e}", 1)
                if attempt < 2:
                    time.sleep(2)
                else:
                    sys.exit(f"❌ Failed after 3 retries for {endpoint}")


# loominar/api/base_client.py
# Core request/response handling + retries
# Low-level HTTP Engine
# Handles all authenticated requests, retry logic, and debug verbosity