"""Drop-off location search — USPS Locations v3.0.

Free tier: no license required.

USPS endpoint:
  GET /locations/v3/dropoff-locations?destinationZIPCode=...&mailClass=...
"""

from __future__ import annotations

from typing import Any

import httpx

from .auth import TokenManager
from .exceptions import APIError, NetworkError, RateLimitError, ValidationError


class LocationsAPI:
    """Find USPS drop-off locations (Post Offices, collection boxes, retailers)."""

    def __init__(self, http: httpx.Client, tokens: TokenManager, base_url: str):
        self._http = http
        self._tokens = tokens
        self._base_url = base_url

    def dropoff(
        self,
        destination_zip: str,
        *,
        mail_class: str = "PARCEL_SELECT",
        origin_zip: str | None = None,
        weight: float | None = None,
        length: float | None = None,
        width: float | None = None,
        height: float | None = None,
    ) -> dict[str, Any]:
        """Find USPS drop-off locations near a destination ZIP.

        Args:
            destination_zip: 5-digit ZIP code to search near.
            mail_class: Mail class for the package (default: PARCEL_SELECT).
            origin_zip: Origin ZIP code (optional, for filtering by route).
            weight: Package weight in pounds (optional).
            length: Package length in inches (optional).
            width: Package width in inches (optional).
            height: Package height in inches (optional).

        Returns:
            Dict with location results from USPS.
        """
        if not destination_zip:
            raise ValidationError("destination_zip is required", field="destination_zip")

        params: dict[str, str] = {
            "destinationZIPCode": destination_zip,
            "mailClass": mail_class,
        }
        if origin_zip:
            params["originZIPCode"] = origin_zip
        if weight is not None:
            params["weight"] = str(weight)
        if length is not None:
            params["length"] = str(length)
        if width is not None:
            params["width"] = str(width)
        if height is not None:
            params["height"] = str(height)

        token = self._tokens.get_oauth_token()
        try:
            resp = self._http.get(
                f"{self._base_url}/locations/v3/dropoff-locations",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as e:
            raise NetworkError(f"Locations request failed: {e}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(retry_after=int(retry_after) if retry_after else None)

        if resp.status_code >= 400:
            raise APIError(
                f"Location search failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        return resp.json()
