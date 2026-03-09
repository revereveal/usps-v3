"""Address validation and city/state lookup — USPS Addresses v3.

Free tier: no license required.

USPS endpoints:
  GET /addresses/v3/address?streetAddress=...&city=...&state=...&ZIPCode=...
  GET /addresses/v3/city-state?ZIPCode=...
"""

from __future__ import annotations

from typing import Any

import httpx

from .auth import TokenManager
from .exceptions import APIError, NetworkError, RateLimitError, ValidationError


class AddressesAPI:
    """Address validation and ZIP code lookup."""

    def __init__(self, http: httpx.Client, tokens: TokenManager, base_url: str):
        self._http = http
        self._tokens = tokens
        self._base_url = base_url

    def validate(
        self,
        street_address: str,
        *,
        secondary_address: str | None = None,
        city: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        zip_plus4: str | None = None,
    ) -> dict[str, Any]:
        """Validate and standardize a US address.

        Args:
            street_address: Street address line (required).
            secondary_address: Apt, Suite, etc.
            city: City name.
            state: 2-letter state code.
            zip_code: 5-digit ZIP code.
            zip_plus4: 4-digit ZIP+4 extension.

        Returns:
            Dict with 'address', 'additionalInfo', 'corrections', 'matches' keys.
            The 'address' dict contains the standardized address fields.
        """
        if not street_address:
            raise ValidationError("street_address is required", field="street_address")

        params: dict[str, str] = {"streetAddress": street_address}
        if secondary_address:
            params["secondaryAddress"] = secondary_address
        if city:
            params["city"] = city
        if state:
            params["state"] = state
        if zip_code:
            params["ZIPCode"] = zip_code
        if zip_plus4:
            params["ZIPPlus4"] = zip_plus4

        return self._request("GET", "/addresses/v3/address", params=params)

    def city_state(self, zip_code: str) -> dict[str, Any]:
        """Look up city and state for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code.

        Returns:
            Dict with city and state information.
        """
        if not zip_code:
            raise ValidationError("zip_code is required", field="zip_code")

        return self._request("GET", "/addresses/v3/city-state", params={"ZIPCode": zip_code})

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        token = self._tokens.get_oauth_token()
        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = self._http.request(
                method,
                f"{self._base_url}{path}",
                headers=headers,
                **kwargs,
            )
        except httpx.HTTPError as e:
            raise NetworkError(f"Request failed: {e}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(retry_after=int(retry_after) if retry_after else None)

        if resp.status_code >= 400:
            raise APIError(
                f"USPS API error ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        return resp.json()
