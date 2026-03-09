"""Main client — the single entry point for the USPS v3 SDK.

Usage:
    from usps_v3 import Client

    client = Client(client_id="...", client_secret="...")
    # or: reads USPS_CLIENT_ID / USPS_CLIENT_SECRET from env
    client = Client()

    result = client.addresses.validate(street_address="1600 Pennsylvania Ave NW", city="Washington", state="DC")
    info = client.tracking.track("9400111899223033005282")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from .addresses import AddressesAPI
from .auth import TokenManager
from .labels import LabelsAPI
from .locations import LocationsAPI
from .prices import PricesAPI
from .standards import StandardsAPI
from .tracking import TrackingAPI

_DEFAULT_BASE_URL = "https://apis.usps.com"
_DEFAULT_TIMEOUT = 30.0


class Client:
    """USPS v3 API client.

    Manages OAuth token lifecycle and provides access to all API modules:
      - client.addresses  — validate(), city_state()
      - client.tracking   — track()
      - client.labels     — create(), void()
      - client.prices     — domestic(), international()
      - client.standards  — estimates()
      - client.locations  — dropoff()

    Args:
        client_id: USPS OAuth client ID. Falls back to USPS_CLIENT_ID env var.
        client_secret: USPS OAuth client secret. Falls back to USPS_CLIENT_SECRET env var.
        base_url: USPS API base URL (default: https://apis.usps.com).
        cache_dir: Directory for token cache (default: ~/.usps-v3).
        timeout: HTTP request timeout in seconds (default: 30).
        crid: USPS Customer Registration ID (for labels/payment auth).
        master_mid: USPS Mailer ID — master (for labels).
        label_mid: USPS Mailer ID — label owner (for labels).
        epa_account: USPS Enterprise Payment Account number (for labels).
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        cache_dir: str | Path | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        crid: str | None = None,
        master_mid: str | None = None,
        label_mid: str | None = None,
        epa_account: str | None = None,
    ):
        resolved_id = client_id or os.environ.get("USPS_CLIENT_ID", "")
        resolved_secret = client_secret or os.environ.get("USPS_CLIENT_SECRET", "")

        if not resolved_id or not resolved_secret:
            raise ValueError(
                "USPS credentials required. Either pass client_id/client_secret "
                "or set USPS_CLIENT_ID/USPS_CLIENT_SECRET environment variables."
            )

        self._base_url = base_url.rstrip("/")

        # Shared HTTP client — connection pooling, keep-alive
        self._http = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "usps-v3-python/1.0.0"},
        )

        # Token manager — handles OAuth lifecycle + file caching
        self._tokens = TokenManager(
            resolved_id,
            resolved_secret,
            base_url=self._base_url,
            cache_dir=cache_dir,
            http_client=self._http,
            crid=crid or os.environ.get("USPS_CRID"),
            master_mid=master_mid or os.environ.get("USPS_MASTER_MID"),
            label_mid=label_mid or os.environ.get("USPS_LABEL_MID"),
            epa_account=epa_account or os.environ.get("USPS_EPA_ACCOUNT"),
        )

        # API modules
        self.addresses = AddressesAPI(self._http, self._tokens, self._base_url)
        self.tracking = TrackingAPI(self._http, self._tokens, self._base_url)
        self.labels = LabelsAPI(self._http, self._tokens, self._base_url)
        self.prices = PricesAPI(self._http, self._tokens, self._base_url)
        self.standards = StandardsAPI(self._http, self._tokens, self._base_url)
        self.locations = LocationsAPI(self._http, self._tokens, self._base_url)

    @property
    def token_status(self) -> dict[str, Any]:
        """Current token status (valid, TTL, scope)."""
        return self._tokens.status

    def refresh_tokens(self) -> dict[str, Any]:
        """Force refresh all tokens."""
        return self._tokens.force_refresh()

    def close(self) -> None:
        """Close HTTP connections and clean up resources."""
        self._tokens.close()
        self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<usps_v3.Client base_url={self._base_url!r}>"
