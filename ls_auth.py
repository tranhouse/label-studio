"""Shared Label Studio authentication helper.

Used by 03_upload_tiles.py and 05_export_to_yolo.py to talk to the Label Studio
REST API. It works with both token types Label Studio issues:

  * Personal Access Token (PAT): a JWT "refresh" token. It is exchanged for a
    short-lived access token, sent as "Authorization: Bearer <access>".
  * Legacy API token: a plain string, sent as "Authorization: Token <key>".

Put the token in the LABEL_STUDIO_TOKEN environment variable before running a script:

    $env:LABEL_STUDIO_TOKEN = 'paste-token-here'
"""
import os

import requests


class LabelStudio:
    """A small Label Studio API client that handles authentication.

    Example:
        ls = LabelStudio("http://localhost:8080")
        projects = ls.request("GET", "/api/projects/").json()
    """

    def __init__(self, base_url, token=None):
        """Store the server address and token, then authenticate.

        Args:
            base_url: Label Studio address, e.g. "http://localhost:8080".
            token: API token. If omitted, read from the LABEL_STUDIO_TOKEN
                environment variable.

        Raises:
            ValueError: If no token is given or set in the environment.
        """
        # Remove a trailing slash so "http://host/" + "/api/..." doesn't become "//api"
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("LABEL_STUDIO_TOKEN")
        if not self.token:
            raise ValueError("Set LABEL_STUDIO_TOKEN (Account & Settings > Access Token in Label Studio).")

        # A Session reuses the connection and keeps the Authorization header for every request
        self.session = requests.Session()
        self.authenticate()

    def authenticate(self):
        """Set the Authorization header for the session.

        A PAT is exchanged at /api/token/refresh for an access token, which expires
        after a few minutes, so long-running scripts call this again to refresh it.
        A legacy token never expires and is used as-is.

        Raises:
            requests.HTTPError: If Label Studio rejects the PAT.
        """
        # PATs are JWTs: three base64 parts joined by dots. Legacy tokens contain no dots.
        if self.token.count(".") == 2:
            r = requests.post(f"{self.base_url}/api/token/refresh",
                              json={"refresh": self.token}, timeout=30)
            r.raise_for_status()
            self.session.headers["Authorization"] = f"Bearer {r.json()['access']}"
        else:
            self.session.headers["Authorization"] = f"Token {self.token}"

    def request(self, method, path, **kwargs):
        """Send an authenticated request to the Label Studio API.

        If the server answers 401 (the access token expired), the client
        re-authenticates once and retries. Uploads are not retried, because their
        file handles have already been read; uploaders call authenticate() before
        each batch instead.

        Args:
            method: HTTP method, e.g. "GET" or "POST".
            path: API path starting with "/", e.g. "/api/projects/".
            **kwargs: Passed to requests (json=, params=, files=, timeout=, ...).

        Returns:
            The requests.Response object for a successful (2xx) response.

        Raises:
            RuntimeError: If the request fails, with the status code and the start
                of the server's error message.
        """
        # Large uploads and exports can be slow, so allow up to 5 minutes by default
        kwargs.setdefault("timeout", 300)
        url = f"{self.base_url}{path}"

        r = self.session.request(method, url, **kwargs)

        # 401 = expired access token: refresh it and try once more (not for file uploads)
        if r.status_code == 401 and "files" not in kwargs:
            self.authenticate()
            r = self.session.request(method, url, **kwargs)

        if not r.ok:
            raise RuntimeError(f"{method} {path} failed ({r.status_code}): {r.text[:500]}")
        return r
