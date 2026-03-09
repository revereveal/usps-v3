"""Package tracking — USPS Tracking v3.2.

Free tier: no license required.

USPS endpoint:
  GET /tracking/v3/tracking/{trackingNumber}?expand=DETAIL|SUMMARY
"""

from __future__ import annotations

from typing import Any, Literal

import httpx

from .auth import TokenManager
from .exceptions import APIError, NetworkError, RateLimitError, ValidationError


class TrackingAPI:
    """Package tracking by tracking number."""

    def __init__(self, http: httpx.Client, tokens: TokenManager, base_url: str):
        self._http = http
        self._tokens = tokens
        self._base_url = base_url

    def track(
        self,
        tracking_number: str,
        *,
        expand: Literal["DETAIL", "SUMMARY"] = "DETAIL",
    ) -> dict[str, Any]:
        """Get tracking information for a package.

        Args:
            tracking_number: USPS tracking number.
            expand: Level of detail — 'DETAIL' (all events) or 'SUMMARY' (latest only).

        Returns:
            Dict with tracking status, events, and delivery info.
        """
        if not tracking_number:
            raise ValidationError("tracking_number is required", field="tracking_number")

        tracking_number = tracking_number.strip()

        token = self._tokens.get_oauth_token()
        try:
            resp = self._http.get(
                f"{self._base_url}/tracking/v3/tracking/{tracking_number}",
                params={"expand": expand},
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as e:
            raise NetworkError(f"Tracking request failed: {e}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(retry_after=int(retry_after) if retry_after else None)

        if resp.status_code >= 400:
            raise APIError(
                f"Tracking failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        return resp.json()
