"""OAuth 2.0 token management for USPS v3 API.

Two-token lifecycle:
  1. OAuth Bearer Token (8h / 28800s) — required for all API calls
  2. Payment Authorization Token (8h) — required for label creation only

Token caching: file-based at ~/.usps-v3/tokens.json with TTL.
Thread-safe: uses threading.Lock for concurrent access.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from .exceptions import AuthError

# 30-minute buffer before actual expiry (matches worker pattern)
_EXPIRY_BUFFER_S = 1800
_DEFAULT_TOKEN_LIFETIME_S = 28800  # 8 hours


class TokenManager:
    """Manages OAuth 2.0 and Payment Authorization tokens for USPS v3."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = "https://apis.usps.com",
        cache_dir: str | Path | None = None,
        http_client: httpx.Client | None = None,
        # Payment Auth credentials (optional — only needed for labels)
        crid: str | None = None,
        master_mid: str | None = None,
        label_mid: str | None = None,
        epa_account: str | None = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url.rstrip("/")
        self._http = http_client
        self._owns_http = http_client is None

        # Payment Auth credentials
        self._crid = crid
        self._master_mid = master_mid
        self._label_mid = label_mid
        self._epa_account = epa_account

        # In-memory token state
        self._oauth_token: str | None = None
        self._oauth_expires_at: float = 0
        self._oauth_scope: str | None = None
        self._payment_token: str | None = None
        self._payment_expires_at: float = 0

        # Thread safety
        self._lock = threading.Lock()

        # File cache
        self._cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".usps-v3"
        self._cache_file = self._cache_dir / "tokens.json"
        self._hydrate_from_cache()

    @property
    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=30.0)
        return self._http

    def get_oauth_token(self) -> str:
        """Get a valid OAuth bearer token, refreshing if needed."""
        with self._lock:
            now = time.time()
            if self._oauth_token and self._oauth_expires_at > now + 60:
                return self._oauth_token
            return self._refresh_oauth()

    def get_payment_token(self) -> str:
        """Get a valid Payment Authorization token, refreshing if needed.

        Requires crid, master_mid, label_mid, epa_account to be set.
        """
        with self._lock:
            now = time.time()
            if self._payment_token and self._payment_expires_at > now + 60:
                return self._payment_token

            # Payment Auth requires a valid OAuth token first
            if not self._oauth_token or self._oauth_expires_at <= now + 60:
                self._refresh_oauth()

            return self._refresh_payment_auth()

    def get_both_tokens(self) -> tuple[str, str]:
        """Get both OAuth and Payment Auth tokens (for label creation)."""
        oauth = self.get_oauth_token()
        payment = self.get_payment_token()
        return oauth, payment

    def force_refresh(self) -> dict[str, Any]:
        """Force refresh both tokens. Returns status dict."""
        with self._lock:
            result: dict[str, Any] = {"oauth": False, "payment": False}
            try:
                self._refresh_oauth()
                result["oauth"] = True
            except AuthError as e:
                result["oauth_error"] = str(e)
            try:
                self._refresh_payment_auth()
                result["payment"] = True
            except AuthError as e:
                result["payment_error"] = str(e)
            return result

    @property
    def status(self) -> dict[str, Any]:
        """Current token status."""
        now = time.time()
        return {
            "oauth": {
                "valid": bool(self._oauth_token and self._oauth_expires_at > now),
                "expires_at": self._oauth_expires_at,
                "ttl_seconds": max(0, int(self._oauth_expires_at - now)),
                "scope": self._oauth_scope,
            },
            "payment": {
                "valid": bool(self._payment_token and self._payment_expires_at > now),
                "expires_at": self._payment_expires_at,
                "ttl_seconds": max(0, int(self._payment_expires_at - now)),
            },
        }

    def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_http and self._http is not None:
            self._http.close()
            self._http = None

    def _refresh_oauth(self) -> str:
        """Refresh OAuth bearer token via client_credentials grant."""
        try:
            resp = self._client.post(
                f"{self._base_url}/oauth2/v3/token",
                json={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "client_credentials",
                },
            )
        except httpx.HTTPError as e:
            raise AuthError(f"OAuth token request failed: {e}") from e

        if resp.status_code != 200:
            raise AuthError(
                f"OAuth token refresh failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        data = resp.json()
        expires_in = int(data.get("expires_in", _DEFAULT_TOKEN_LIFETIME_S))
        self._oauth_token = data["access_token"]
        self._oauth_expires_at = time.time() + expires_in - _EXPIRY_BUFFER_S
        self._oauth_scope = data.get("scope")
        self._persist_cache()
        return self._oauth_token

    def _refresh_payment_auth(self) -> str:
        """Refresh Payment Authorization token (requires OAuth + enrollment credentials)."""
        if not self._oauth_token:
            raise AuthError("Cannot refresh Payment Auth without valid OAuth token")

        if not all([self._crid, self._master_mid, self._label_mid, self._epa_account]):
            raise AuthError(
                "Payment Auth requires crid, master_mid, label_mid, and epa_account. "
                "These come from your USPS Business Customer Gateway enrollment."
            )

        try:
            resp = self._client.post(
                f"{self._base_url}/payments/v3/payment-authorization",
                json={
                    "roles": [
                        {
                            "roleName": "PAYER",
                            "CRID": self._crid,
                            "MID": self._master_mid,
                            "manifestMID": self._master_mid,
                            "accountType": "EPS",
                            "accountNumber": self._epa_account,
                        },
                        {
                            "roleName": "LABEL_OWNER",
                            "CRID": self._crid,
                            "MID": self._label_mid,
                            "manifestMID": self._master_mid,
                            "accountType": "EPS",
                            "accountNumber": self._epa_account,
                        },
                    ],
                },
                headers={"Authorization": f"Bearer {self._oauth_token}"},
            )
        except httpx.HTTPError as e:
            raise AuthError(f"Payment Auth request failed: {e}") from e

        if resp.status_code != 200:
            raise AuthError(
                f"Payment Auth refresh failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        data = resp.json()
        expires_in = int(data.get("expiresIn", data.get("expires_in", _DEFAULT_TOKEN_LIFETIME_S)))
        self._payment_token = data["paymentAuthorizationToken"]
        self._payment_expires_at = time.time() + expires_in - _EXPIRY_BUFFER_S
        self._persist_cache()
        return self._payment_token

    def _hydrate_from_cache(self) -> None:
        """Load cached tokens from disk."""
        if not self._cache_file.exists():
            return
        try:
            data = json.loads(self._cache_file.read_text())
            now = time.time()
            if data.get("oauth_expires_at", 0) > now:
                self._oauth_token = data["oauth_token"]
                self._oauth_expires_at = data["oauth_expires_at"]
                self._oauth_scope = data.get("oauth_scope")
            if data.get("payment_expires_at", 0) > now:
                self._payment_token = data.get("payment_token")
                self._payment_expires_at = data.get("payment_expires_at", 0)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Corrupt cache — will refresh on next call

    def _persist_cache(self) -> None:
        """Save current tokens to disk."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            # Restrictive permissions — tokens are sensitive
            data = {
                "oauth_token": self._oauth_token,
                "oauth_expires_at": self._oauth_expires_at,
                "oauth_scope": self._oauth_scope,
                "payment_token": self._payment_token,
                "payment_expires_at": self._payment_expires_at,
                "cached_at": time.time(),
            }
            self._cache_file.write_text(json.dumps(data))
            try:
                os.chmod(self._cache_file, 0o600)
            except OSError:
                pass  # Windows doesn't support chmod the same way
        except OSError:
            pass  # Non-fatal — tokens are in memory
