"""Tests for address validation and city/state lookup."""

import httpx
import pytest

from usps_v3.exceptions import APIError, RateLimitError, ValidationError


USPS_ADDRESS_RESPONSE = {
    "address": {
        "streetAddress": "1600 PENNSYLVANIA AVE NW",
        "city": "WASHINGTON",
        "state": "DC",
        "ZIPCode": "20500",
        "ZIPPlus4": "0005",
    },
    "additionalInfo": {
        "deliveryPoint": "00",
        "DPVConfirmation": "Y",
        "business": "Y",
        "vacant": "N",
    },
    "corrections": None,
    "matches": None,
}

CITY_STATE_RESPONSE = {
    "city": "NEW YORK",
    "state": "NY",
    "ZIPCode": "10001",
}


class TestValidate:
    """Address validation tests."""

    def test_validate_success(self, client, mock_api):
        mock_api.get("/addresses/v3/address").mock(
            return_value=httpx.Response(200, json=USPS_ADDRESS_RESPONSE)
        )
        result = client.addresses.validate(
            street_address="1600 Pennsylvania Ave NW",
            city="Washington",
            state="DC",
            zip_code="20500",
        )
        assert result["address"]["streetAddress"] == "1600 PENNSYLVANIA AVE NW"
        assert result["address"]["ZIPPlus4"] == "0005"

    def test_validate_requires_street(self, client):
        with pytest.raises(ValidationError, match="street_address"):
            client.addresses.validate(street_address="")

    def test_validate_with_secondary(self, client, mock_api):
        mock_api.get("/addresses/v3/address").mock(
            return_value=httpx.Response(200, json=USPS_ADDRESS_RESPONSE)
        )
        result = client.addresses.validate(
            street_address="123 Main St",
            secondary_address="Apt 4B",
            city="New York",
            state="NY",
        )
        assert result is not None

    def test_validate_zip_only(self, client, mock_api):
        mock_api.get("/addresses/v3/address").mock(
            return_value=httpx.Response(200, json=USPS_ADDRESS_RESPONSE)
        )
        result = client.addresses.validate(
            street_address="1600 Pennsylvania Ave NW",
            zip_code="20500",
        )
        assert result["address"]["ZIPCode"] == "20500"

    def test_validate_api_error(self, client, mock_api):
        mock_api.get("/addresses/v3/address").mock(
            return_value=httpx.Response(404, text="Address not found")
        )
        with pytest.raises(APIError, match="404"):
            client.addresses.validate(street_address="Nowhere St")

    def test_validate_rate_limit(self, client, mock_api):
        mock_api.get("/addresses/v3/address").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "60"})
        )
        with pytest.raises(RateLimitError) as exc_info:
            client.addresses.validate(street_address="Any St")
        assert exc_info.value.retry_after == 60


class TestCityState:
    """City/state lookup tests."""

    def test_city_state_success(self, client, mock_api):
        mock_api.get("/addresses/v3/city-state").mock(
            return_value=httpx.Response(200, json=CITY_STATE_RESPONSE)
        )
        result = client.addresses.city_state("10001")
        assert result["city"] == "NEW YORK"
        assert result["state"] == "NY"

    def test_city_state_requires_zip(self, client):
        with pytest.raises(ValidationError, match="zip_code"):
            client.addresses.city_state("")

    def test_city_state_api_error(self, client, mock_api):
        mock_api.get("/addresses/v3/city-state").mock(
            return_value=httpx.Response(400, text="Invalid ZIP")
        )
        with pytest.raises(APIError, match="400"):
            client.addresses.city_state("00000")
