"""Tests for service standards (delivery time estimates)."""

import httpx
import pytest
import respx

from usps_v3.exceptions import APIError, ValidationError


STANDARDS_RESPONSE = {
    "standards": [
        {
            "mailClass": "PRIORITY_MAIL",
            "originZIP": "10001",
            "destinationZIP": "90210",
            "days": "2",
            "effectiveAcceptanceDate": "2026-03-09",
            "scheduledDeliveryDate": "2026-03-11",
        },
        {
            "mailClass": "USPS_GROUND_ADVANTAGE",
            "originZIP": "10001",
            "destinationZIP": "90210",
            "days": "5",
            "effectiveAcceptanceDate": "2026-03-09",
            "scheduledDeliveryDate": "2026-03-14",
        },
    ],
}


class TestEstimates:
    """Service standards estimation tests."""

    def test_estimates_success(self, client, mock_api):
        mock_api.get("/service-standards/v3/estimates").mock(
            return_value=httpx.Response(200, json=STANDARDS_RESPONSE)
        )
        result = client.standards.estimates("10001", "90210")
        assert "standards" in result

    def test_estimates_with_mail_class(self, client, mock_api):
        mock_api.get("/service-standards/v3/estimates").mock(
            return_value=httpx.Response(200, json=STANDARDS_RESPONSE)
        )
        result = client.standards.estimates("10001", "90210", mail_class="PRIORITY_MAIL")
        assert result is not None

    def test_estimates_requires_origin(self, client):
        with pytest.raises(ValidationError, match="origin_zip"):
            client.standards.estimates("", "90210")

    def test_estimates_requires_destination(self, client):
        with pytest.raises(ValidationError, match="destination_zip"):
            client.standards.estimates("10001", "")

    def test_estimates_api_error(self, client, mock_api):
        mock_api.get("/service-standards/v3/estimates").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(APIError, match="500"):
            client.standards.estimates("10001", "90210")
