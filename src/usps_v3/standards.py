"""Service standards (delivery time estimates) — USPS Service Standards v3.0.

Free tier: no license required.

USPS endpoint:
  GET /service-standards/v3/estimates?originZIPCode=...&destinationZIPCode=...&mailClass=...
"""

from __future__ import annotations

from typing import Any

import httpx

from .auth import TokenManager
from .exceptions import APIError, NetworkError, RateLimitError, ValidationError


class StandardsAPI:
    """Delivery time estimates between ZIP codes."""

    def __init__(self, http: httpx.Client, tokens: TokenManager, base_url: str):
        self._http = http
        self._tokens = tokens
        self._base_url = base_url

    def estimates(
        self,
        origin_zip: str,
        destination_zip: str,
        *,
        mail_class: str | None = None,
        acceptance_date: str | None = None,
    ) -> dict[str, Any]:
        """Get delivery time estimates between two ZIP codes.

        Args:
            origin_zip: Origin 5-digit ZIP code.
            destination_zip: Destination 5-digit ZIP code.
            mail_class: Filter to specific mail class (optional).
            acceptance_date: ISO date string for acceptance date.

        Returns:
            Dict with delivery estimates per mail class.
        """
        if not origin_zip:
            raise ValidationError("origin_zip is required", field="origin_zip")
        if not destination_zip:
            raise ValidationError("destination_zip is required", field="destination_zip")

        params: dict[str, str] = {
            "originZIPCode": origin_zip,
            "destinationZIPCode": destination_zip,
        }
        if mail_class:
            params["mailClass"] = mail_class
        if acceptance_date:
            params["acceptanceDate"] = acceptance_date

        token = self._tokens.get_oauth_token()
        try:
            resp = self._http.get(
                f"{self._base_url}/service-standards/v3/estimates",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as e:
            raise NetworkError(f"Service standards request failed: {e}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(retry_after=int(retry_after) if retry_after else None)

        if resp.status_code >= 400:
            raise APIError(
                f"Service standards failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        return resp.json()
