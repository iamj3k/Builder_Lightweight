from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


@dataclass
class AuthResult:
    access_token: str
    refresh_token: str | None
    expires_in: int


@dataclass
class TokenSnapshot:
    access_token: str
    refresh_token: str
    expires_at: float


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

    def __init__(self, client_id: str, redirect_uri: str, scopes: list[str], token_store_path: Path) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.token_store_path = token_store_path
        self.token_snapshot = self._load_token_snapshot()

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

        auth = self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "code_verifier": verifier,
            }
        )
        if auth.refresh_token:
            self._save_token_snapshot(auth)
        return auth

    def ensure_access_token(self, min_validity_seconds: int = 120) -> str:
        now = time.time()
        if self.token_snapshot and self.token_snapshot.expires_at - now > min_validity_seconds:
            return self.token_snapshot.access_token

        if not self.token_snapshot or not self.token_snapshot.refresh_token:
            raise RuntimeError("Reconnect required")

        refreshed = self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.token_snapshot.refresh_token,
                "client_id": self.client_id,
            }
        )
        self._save_token_snapshot(refreshed)
        return refreshed.access_token

    def connection_label(self) -> str:
        try:
            self.ensure_access_token()
            return "Connected"
        except Exception:
            return "Reconnect"

    def _token_request(self, payload: dict[str, str]) -> AuthResult:
        token_data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(self.TOKEN_URL, data=token_data, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(request, timeout=30) as response:
            parsed_payload = json.loads(response.read().decode("utf-8"))

        return AuthResult(
            access_token=parsed_payload["access_token"],
            refresh_token=parsed_payload.get("refresh_token") or payload.get("refresh_token"),
            expires_in=int(parsed_payload.get("expires_in", 0)),
        )

    def _save_token_snapshot(self, auth: AuthResult) -> None:
        if not auth.refresh_token:
            return
        expires_at = time.time() + max(auth.expires_in, 1)
        encrypted = _protect_windows(auth.refresh_token)
        snapshot = {
            "access_token": auth.access_token,
            "refresh_token_protected": base64.b64encode(encrypted).decode("ascii"),
            "expires_at": expires_at,
        }
        self.token_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_store_path.write_text(json.dumps(snapshot), encoding="utf-8")
        self.token_snapshot = TokenSnapshot(
            access_token=auth.access_token,
            refresh_token=auth.refresh_token,
            expires_at=expires_at,
        )

    def _load_token_snapshot(self) -> TokenSnapshot | None:
        if not self.token_store_path.exists():
            return None
        payload = json.loads(self.token_store_path.read_text(encoding="utf-8"))
        refresh_token_blob = base64.b64decode(payload["refresh_token_protected"])
        refresh_token = _unprotect_windows(refresh_token_blob)
        return TokenSnapshot(
            access_token=str(payload.get("access_token", "")),
            refresh_token=refresh_token,
            expires_at=float(payload.get("expires_at", 0)),
        )

    @staticmethod
    def _code_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def _code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _protect_windows(secret: str) -> bytes:
    if not secret:
        raise RuntimeError("Missing refresh token")
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Windows secure token storage is required")

    raw = secret.encode("utf-8")
    in_buffer = ctypes.create_string_buffer(raw)
    in_blob = _DataBlob(len(raw), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    out_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise RuntimeError("Unable to securely store refresh token")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _unprotect_windows(ciphertext: bytes) -> str:
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Windows secure token storage is required")

    in_buffer = ctypes.create_string_buffer(ciphertext)
    in_blob = _DataBlob(len(ciphertext), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    out_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise RuntimeError("Unable to read stored refresh token")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)
