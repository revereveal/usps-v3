"""Tests for label creation and void."""

import httpx
import pytest

from usps_v3.exceptions import APIError, AuthError, ValidationError


FROM_ADDRESS = {
    "streetAddress": "123 Sender St",
    "city": "New York",
    "state": "NY",
    "ZIPCode": "10001",
}

TO_ADDRESS = {
    "streetAddress": "456 Recipient Ave",
    "city": "Los Angeles",
    "state": "CA",
    "ZIPCode": "90001",
}

LABEL_METADATA = {
    "trackingNumber": "9400111899223033005282",
    "postage": 8.95,
    "zone": "08",
    "commitment": {"name": "2-Day", "scheduleDeliveryDate": "2026-03-11"},
    "SKU": "DPXX0XXXXC00000",
    "bannerText": "USPS PRIORITY MAIL",
}


class TestLabelCreate:
    """Label creation tests."""

    def test_create_success(self, client_with_payment, mock_api_with_payment):
        # Mock JSON-only response (TEM style)
        mock_api_with_payment.post("/labels/v3/label").mock(
            return_value=httpx.Response(200, json=LABEL_METADATA)
        )
        result = client_with_payment.labels.create(
            from_address=FROM_ADDRESS,
            to_address=TO_ADDRESS,
            mail_class="PRIORITY_MAIL",
            weight=2.0,
        )
        assert result["trackingNumber"] == "9400111899223033005282"
        assert result["postage"] == 8.95

    def test_create_requires_from_address(self, client_with_payment):
        with pytest.raises(ValidationError, match="from_address"):
            client_with_payment.labels.create(
                from_address={},
                to_address=TO_ADDRESS,
                mail_class="PRIORITY_MAIL",
                weight=2.0,
            )

    def test_create_requires_to_address(self, client_with_payment):
        with pytest.raises(ValidationError, match="to_address"):
            client_with_payment.labels.create(
                from_address=FROM_ADDRESS,
                to_address={},
                mail_class="PRIORITY_MAIL",
                weight=2.0,
            )

    def test_create_requires_mail_class(self, client_with_payment):
        with pytest.raises(ValidationError, match="mail_class"):
            client_with_payment.labels.create(
                from_address=FROM_ADDRESS,
                to_address=TO_ADDRESS,
                mail_class="",
                weight=2.0,
            )

    def test_create_validates_mail_class(self, client_with_payment):
        with pytest.raises(ValidationError, match="Invalid mail_class"):
            client_with_payment.labels.create(
                from_address=FROM_ADDRESS,
                to_address=TO_ADDRESS,
                mail_class="FAKE_MAIL",
                weight=2.0,
            )

    def test_create_without_payment_creds(self, client, mock_api):
        # Standard client has no payment credentials
        with pytest.raises(AuthError, match="requires crid"):
            client.labels.create(
                from_address=FROM_ADDRESS,
                to_address=TO_ADDRESS,
                mail_class="PRIORITY_MAIL",
                weight=2.0,
            )


class TestLabelVoid:
    """Label void/refund tests."""

    def test_void_success(self, client, mock_api):
        mock_api.delete("/labels/v3/label/9400111899223033005282").mock(
            return_value=httpx.Response(200, content=b"")
        )
        result = client.labels.void("9400111899223033005282")
        assert result["status"] == "voided"
        assert result["trackingNumber"] == "9400111899223033005282"

    def test_void_requires_tracking_number(self, client):
        with pytest.raises(ValidationError, match="tracking_number"):
            client.labels.void("")

    def test_void_api_error(self, client, mock_api):
        mock_api.delete("/labels/v3/label/INVALID").mock(
            return_value=httpx.Response(404, text="Label not found")
        )
        with pytest.raises(APIError, match="404"):
            client.labels.void("INVALID")
