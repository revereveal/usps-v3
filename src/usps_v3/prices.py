"""Domestic and international rate quotes — USPS Prices v3.0.

USPS endpoints:
  POST /prices/v3/total-rates/search                    (domestic)
  POST /international-prices/v3/total-rates/search      (international)
"""

from __future__ import annotations

from typing import Any

import httpx

from .auth import TokenManager
from .exceptions import APIError, NetworkError, RateLimitError, ValidationError

INTL_MAIL_CLASSES = frozenset({
    "PRIORITY_MAIL_EXPRESS_INTERNATIONAL",
    "PRIORITY_MAIL_INTERNATIONAL",
    "FIRST-CLASS_PACKAGE_INTERNATIONAL_SERVICE",
    "GLOBAL_EXPRESS_GUARANTEED",
})


class PricesAPI:
    """Domestic and international rate quotes."""

    def __init__(self, http: httpx.Client, tokens: TokenManager, base_url: str):
        self._http = http
        self._tokens = tokens
        self._base_url = base_url

    def domestic(
        self,
        origin_zip: str,
        destination_zip: str,
        weight: float,
        *,
        length: float = 6,
        width: float = 4,
        height: float = 1,
        mail_class: str | None = None,
        processing_category: str | None = None,
        rate_indicator: str | None = None,
        price_type: str | None = None,
        mailing_date: str | None = None,
        account_type: str | None = None,
        account_number: str | None = None,
        item_value: float | None = None,
        extra_services: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Get domestic rate quotes for a package.

        Args:
            origin_zip: Origin 5-digit ZIP code.
            destination_zip: Destination 5-digit ZIP code.
            weight: Package weight in pounds.
            length: Package length in inches (default 6).
            width: Package width in inches (default 4).
            height: Package height in inches (default 1).
            mail_class: Filter to specific mail class (optional — omit for all classes).
            processing_category: 'MACHINABLE', 'NON_MACHINABLE', etc.
            rate_indicator: Rate type (e.g. 'SP' for single piece).
            price_type: 'RETAIL' or 'COMMERCIAL'.
            mailing_date: ISO date string.
            account_type: 'EPS', 'PERMIT', etc.
            account_number: Account number for commercial pricing.
            item_value: Declared value for insurance quotes.
            extra_services: List of extra service dicts.

        Returns:
            Dict with 'rates' (USPS response) and 'input' summary.
        """
        for field, value, name in [
            (origin_zip, origin_zip, "origin_zip"),
            (destination_zip, destination_zip, "destination_zip"),
        ]:
            if not value:
                raise ValidationError(f"{name} is required", field=name)
        if weight is None or weight <= 0:
            raise ValidationError("weight must be greater than 0", field="weight")

        body: dict[str, Any] = {
            "originZIPCode": origin_zip,
            "destinationZIPCode": destination_zip,
            "weight": weight,
            "length": length,
            "width": width,
            "height": height,
        }
        if mail_class:
            body["mailClass"] = mail_class
        if processing_category:
            body["processingCategory"] = processing_category
        if rate_indicator:
            body["rateIndicator"] = rate_indicator
        if price_type:
            body["priceType"] = price_type
        if mailing_date:
            body["mailingDate"] = mailing_date
        if account_type:
            body["accountType"] = account_type
        if account_number:
            body["accountNumber"] = account_number
        if item_value is not None:
            body["itemValue"] = item_value
        if extra_services:
            body["extraServices"] = extra_services

        data = self._request("POST", "/prices/v3/total-rates/search", json=body)
        return {
            "rates": data,
            "input": {"origin": origin_zip, "destination": destination_zip, "weight": weight},
        }

    def international(
        self,
        origin_zip: str,
        destination_country_code: str,
        weight: float,
        *,
        length: float = 6,
        width: float = 4,
        height: float = 1,
        mail_class: str | None = None,
        price_type: str | None = None,
        mailing_date: str | None = None,
        account_type: str | None = None,
        account_number: str | None = None,
        item_value: float | None = None,
        extra_services: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Get international rate quotes.

        Args:
            origin_zip: Origin 5-digit ZIP code.
            destination_country_code: ISO 3166-1 alpha-2 country code (e.g. 'CA', 'GB', 'JP').
            weight: Package weight in pounds.
            mail_class: International mail class (optional).
            Other args same as domestic().

        Returns:
            Dict with 'rates' (USPS response) and 'input' summary.
        """
        if not origin_zip:
            raise ValidationError("origin_zip is required", field="origin_zip")
        if not destination_country_code:
            raise ValidationError("destination_country_code is required", field="destination_country_code")
        if len(destination_country_code) != 2:
            raise ValidationError("destination_country_code must be a 2-letter ISO code", field="destination_country_code")
        if weight is None or weight <= 0:
            raise ValidationError("weight must be greater than 0", field="weight")

        if mail_class and mail_class not in INTL_MAIL_CLASSES:
            raise ValidationError(
                f"Invalid international mail_class '{mail_class}'. Valid: {', '.join(sorted(INTL_MAIL_CLASSES))}",
                field="mail_class",
            )

        body: dict[str, Any] = {
            "originZIPCode": origin_zip,
            "destinationCountryCode": destination_country_code.upper(),
            "weight": weight,
            "length": length,
            "width": width,
            "height": height,
        }
        if mail_class:
            body["mailClass"] = mail_class
        if price_type:
            body["priceType"] = price_type
        if mailing_date:
            body["mailingDate"] = mailing_date
        if account_type:
            body["accountType"] = account_type
        if account_number:
            body["accountNumber"] = account_number
        if item_value is not None:
            body["itemValue"] = item_value
        if extra_services:
            body["extraServices"] = extra_services

        data = self._request("POST", "/international-prices/v3/total-rates/search", json=body)
        return {
            "rates": data,
            "input": {"origin": origin_zip, "destination": destination_country_code.upper(), "weight": weight},
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        token = self._tokens.get_oauth_token()
        headers = {"Authorization": f"Bearer {token}"}
        if "json" in kwargs:
            headers["Content-Type"] = "application/json"

        try:
            resp = self._http.request(
                method,
                f"{self._base_url}{path}",
                headers=headers,
                **kwargs,
            )
        except httpx.HTTPError as e:
            raise NetworkError(f"Price request failed: {e}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(retry_after=int(retry_after) if retry_after else None)

        if resp.status_code >= 400:
            raise APIError(
                f"Price lookup failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        return resp.json()
