from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


@dataclass
class AuthResult:
    access_token: str
    refresh_token: str | None
    expires_in: int


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        code = query.get("code", [None])[0]

        if code:
            _CallbackHandler.auth_code = code
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Login successful. You can close this window.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter.")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class EveSsoClient:
    AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
    TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"

    def __init__(self, client_id: str, redirect_uri: str, scopes: list[str]) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scopes = scopes

    def login(self) -> AuthResult:
        verifier = self._code_verifier()
        challenge = self._code_challenge(verifier)

        parsed = urllib.parse.urlparse(self.redirect_uri)
        server = HTTPServer((parsed.hostname or "127.0.0.1", parsed.port or 8799), _CallbackHandler)
        _CallbackHandler.auth_code = None

        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        params = {
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "scope": " ".join(self.scopes),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"
        webbrowser.open(auth_url)

        thread.join(timeout=180)
        server.server_close()

        code = _CallbackHandler.auth_code
        if not code:
            raise RuntimeError("EVE SSO login timed out or was cancelled")

        token_data = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "code_verifier": verifier,
            }
        ).encode("utf-8")
        request = urllib.request.Request(self.TOKEN_URL, data=token_data, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")

        import json

        parsed_payload = json.loads(payload)
        return AuthResult(
            access_token=parsed_payload["access_token"],
            refresh_token=parsed_payload.get("refresh_token"),
            expires_in=int(parsed_payload.get("expires_in", 0)),
        )

    @staticmethod
    def _code_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def _code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
