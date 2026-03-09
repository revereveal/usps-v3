"""Domestic label creation, download, void, and listing — USPS Labels v3.0.

Requires Payment Authorization token (USPS enrollment + COP claims linking).

USPS endpoints:
  POST   /labels/v3/label                    (create — returns multipart: JSON metadata + PDF)
  DELETE /labels/v3/label/{trackingNumber}    (void/refund)
"""

from __future__ import annotations

from typing import Any

import httpx

from .auth import TokenManager
from .exceptions import APIError, AuthError, NetworkError, RateLimitError, ValidationError

# Valid domestic mail classes
MAIL_CLASSES = frozenset({
    "PRIORITY_MAIL_EXPRESS",
    "PRIORITY_MAIL",
    "FIRST-CLASS_PACKAGE_SERVICE",
    "PARCEL_SELECT",
    "LIBRARY_MAIL",
    "MEDIA_MAIL",
    "BOUND_PRINTED_MATTER",
    "USPS_GROUND_ADVANTAGE",
})


class LabelsAPI:
    """Domestic label creation and management."""

    def __init__(self, http: httpx.Client, tokens: TokenManager, base_url: str):
        self._http = http
        self._tokens = tokens
        self._base_url = base_url

    def create(
        self,
        from_address: dict[str, Any],
        to_address: dict[str, Any],
        mail_class: str,
        weight: float,
        *,
        image_type: str = "PDF",
        label_type: str = "4X6LABEL",
        rate_indicator: str = "SP",
        length: float = 12,
        width: float = 9,
        height: float = 1,
        processing_category: str = "MACHINABLE",
        mailing_date: str | None = None,
        extra_services: list[dict[str, Any]] | None = None,
        package_value: float | None = None,
        return_label: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a domestic shipping label.

        This calls the USPS Labels v3 API which returns a multipart response
        containing label metadata (JSON) and the label image (PDF). The SDK
        parses the multipart response and returns the metadata as a dict.

        Args:
            from_address: Sender address dict with keys: streetAddress, city, state, ZIPCode, etc.
            to_address: Recipient address dict.
            mail_class: USPS mail class (e.g. 'PRIORITY_MAIL', 'USPS_GROUND_ADVANTAGE').
            weight: Package weight in pounds.
            image_type: Label image format — 'PDF' (default) or 'PNG'.
            label_type: Label size — '4X6LABEL' (default).
            rate_indicator: Rate type — 'SP' (single piece, default).
            length: Package length in inches.
            width: Package width in inches.
            height: Package height in inches.
            processing_category: 'MACHINABLE' (default) or 'NON_MACHINABLE'.
            mailing_date: ISO date string (defaults to today).
            extra_services: List of extra service dicts.
            package_value: Declared value for insurance.
            return_label: Whether this is a return label.
            idempotency_key: Optional key to prevent duplicate label creation.

        Returns:
            Dict with trackingNumber, postage, zone, commitment, SKU, bannerText, labelData.
            labelData contains the raw PDF/PNG bytes if available.

        Raises:
            AuthError: If Payment Authorization token is unavailable.
            ValidationError: If required fields are missing.
        """
        if not from_address:
            raise ValidationError("from_address is required", field="from_address")
        if not to_address:
            raise ValidationError("to_address is required", field="to_address")
        if not mail_class:
            raise ValidationError("mail_class is required", field="mail_class")
        if mail_class not in MAIL_CLASSES:
            raise ValidationError(
                f"Invalid mail_class '{mail_class}'. Valid: {', '.join(sorted(MAIL_CLASSES))}",
                field="mail_class",
            )

        # Get both tokens (OAuth + Payment Auth)
        try:
            oauth_token, payment_token = self._tokens.get_both_tokens()
        except AuthError:
            raise

        if not payment_token:
            raise AuthError(
                "Payment Authorization token unavailable. "
                "Check USPS enrollment: COP claims linking, CRID, MIDs, EPA account."
            )

        import datetime

        label_request = {
            "imageInfo": {
                "imageType": image_type,
                "labelType": label_type,
                "receiptOption": "NONE",
                "suppressPostage": False,
                "suppressMailDate": False,
                "returnLabel": return_label,
            },
            "toAddress": to_address,
            "fromAddress": from_address,
            "packageDescription": {
                "mailClass": mail_class,
                "rateIndicator": rate_indicator,
                "weightUOM": "lb",
                "weight": weight,
                "dimensionsUOM": "in",
                "length": length,
                "width": width,
                "height": height,
                "processingCategory": processing_category,
                "mailingDate": mailing_date or datetime.date.today().isoformat(),
                "destinationEntryFacilityType": "NONE",
            },
        }

        if extra_services:
            label_request["packageDescription"]["extraServices"] = extra_services
        if package_value is not None:
            label_request["packageDescription"]["packageOptions"] = {"packageValue": package_value}

        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "X-Payment-Authorization-Token": payment_token,
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            resp = self._http.post(
                f"{self._base_url}/labels/v3/label",
                headers=headers,
                content=_json_bytes(label_request),
            )
        except httpx.HTTPError as e:
            raise NetworkError(f"Label creation request failed: {e}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(retry_after=int(retry_after) if retry_after else None)

        if resp.status_code >= 400:
            raise APIError(
                f"Label creation failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        # Parse response — USPS returns multipart (JSON metadata + PDF image)
        # or plain JSON in test environments
        content_type = resp.headers.get("content-type", "")
        metadata: dict[str, Any] = {}
        label_data: bytes | None = None

        if "multipart" in content_type:
            # Parse multipart boundary
            metadata, label_data = _parse_multipart(resp)
        else:
            metadata = resp.json()

        result = {
            "trackingNumber": metadata.get("trackingNumber"),
            "postage": metadata.get("postage"),
            "zone": metadata.get("zone"),
            "commitment": metadata.get("commitment"),
            "SKU": metadata.get("SKU"),
            "bannerText": metadata.get("bannerText"),
        }
        if label_data:
            result["labelData"] = label_data

        return result

    def void(self, tracking_number: str) -> dict[str, Any]:
        """Void/refund a label by tracking number.

        Args:
            tracking_number: The tracking number of the label to void.

        Returns:
            Dict with void confirmation from USPS.
        """
        if not tracking_number:
            raise ValidationError("tracking_number is required", field="tracking_number")

        token = self._tokens.get_oauth_token()
        try:
            resp = self._http.delete(
                f"{self._base_url}/labels/v3/label/{tracking_number}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as e:
            raise NetworkError(f"Label void request failed: {e}") from e

        if resp.status_code == 429:
            raise RateLimitError()

        if resp.status_code >= 400:
            raise APIError(
                f"Label void failed ({resp.status_code}): {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        # USPS may return empty 200 on successful void
        if resp.content:
            return resp.json()
        return {"status": "voided", "trackingNumber": tracking_number}


def _json_bytes(obj: Any) -> bytes:
    """Serialize to JSON bytes (avoids httpx auto-serialization issues with nested dicts)."""
    import json

    return json.dumps(obj).encode("utf-8")


def _parse_multipart(resp: httpx.Response) -> tuple[dict[str, Any], bytes | None]:
    """Parse a USPS multipart response into metadata dict and label bytes."""
    import json

    content_type = resp.headers.get("content-type", "")
    # Extract boundary from content-type header
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[9:].strip('"')
            break

    if not boundary:
        # Fallback: try to parse as JSON
        return resp.json(), None

    raw = resp.content
    separator = f"--{boundary}".encode()
    parts = raw.split(separator)

    metadata: dict[str, Any] = {}
    label_data: bytes | None = None

    for part in parts:
        if not part or part == b"--\r\n" or part == b"--":
            continue

        # Split headers from body
        if b"\r\n\r\n" in part:
            header_section, body = part.split(b"\r\n\r\n", 1)
        elif b"\n\n" in part:
            header_section, body = part.split(b"\n\n", 1)
        else:
            continue

        header_text = header_section.decode("utf-8", errors="replace").lower()

        if "labelmetadata" in header_text or "application/json" in header_text:
            try:
                # Strip trailing boundary markers
                json_text = body.rstrip(b"\r\n").decode("utf-8")
                metadata = json.loads(json_text)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        elif "labelimage" in header_text or "application/pdf" in header_text or "image/png" in header_text:
            label_data = body.rstrip(b"\r\n")

    return metadata, label_data
