"""Shared Label Studio authentication helper.

Works with both token types Label Studio issues:
  * Personal Access Token (PAT, a JWT refresh token) -> exchanged for a short-lived access token
  * Legacy API token -> sent as "Token <key>"
Set the token in the LABEL_STUDIO_TOKEN environment variable.
"""
import os
import requests


class LabelStudio:
    def __init__(self, base_url, token=None):
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("LABEL_STUDIO_TOKEN")
        if not self.token:
            raise ValueError("Set LABEL_STUDIO_TOKEN (Account & Settings > Access Token in Label Studio).")
        self.session = requests.Session()
        self.authenticate()

    def authenticate(self):
        # PATs are JWTs (three dot-separated parts); legacy tokens are plain hex
        if self.token.count(".") == 2:
            r = requests.post(f"{self.base_url}/api/token/refresh",
                              json={"refresh": self.token}, timeout=30)
            r.raise_for_status()
            self.session.headers["Authorization"] = f"Bearer {r.json()['access']}"
        else:
            self.session.headers["Authorization"] = f"Token {self.token}"

    def request(self, method, path, **kwargs):
        """Send a request; on 401 (expired access token) re-authenticate once and retry.
        File uploads cannot be replayed, so uploaders call authenticate() before each batch."""
        kwargs.setdefault("timeout", 300)
        url = f"{self.base_url}{path}"
        r = self.session.request(method, url, **kwargs)
        if r.status_code == 401 and "files" not in kwargs:
            self.authenticate()
            r = self.session.request(method, url, **kwargs)
        if not r.ok:
            raise RuntimeError(f"{method} {path} failed ({r.status_code}): {r.text[:500]}")
        return r
