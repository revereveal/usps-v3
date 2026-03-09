"""Tests for domestic and international pricing."""

import httpx
import pytest
import respx

from usps_v3.exceptions import APIError, RateLimitError, ValidationError


DOMESTIC_RATES_RESPONSE = {
    "rateOptions": [
        {
            "mailClass": "PRIORITY_MAIL",
            "totalBasePrice": 8.95,
            "totalPrice": 8.95,
            "zone": "04",
            "commitment": {"name": "2-Day", "scheduleDeliveryDate": "2026-03-11"},
        },
        {
            "mailClass": "USPS_GROUND_ADVANTAGE",
            "totalBasePrice": 5.25,
            "totalPrice": 5.25,
            "zone": "04",
            "commitment": {"name": "2-5 Days"},
        },
    ],
}

INTL_RATES_RESPONSE = {
    "rateOptions": [
        {
            "mailClass": "PRIORITY_MAIL_INTERNATIONAL",
            "totalBasePrice": 42.50,
            "totalPrice": 42.50,
        },
    ],
}


class TestDomesticPrices:
    """Domestic rate quote tests."""

    def test_domestic_success(self, client, mock_api):
        mock_api.post("/prices/v3/total-rates/search").mock(
            return_value=httpx.Response(200, json=DOMESTIC_RATES_RESPONSE)
        )
        result = client.prices.domestic("10001", "90210", 2.5)
        assert "rates" in result
        assert result["input"]["origin"] == "10001"
        assert result["input"]["destination"] == "90210"
        assert result["input"]["weight"] == 2.5

    def test_domestic_requires_origin_zip(self, client):
        with pytest.raises(ValidationError, match="origin_zip"):
            client.prices.domestic("", "90210", 2.5)

    def test_domestic_requires_destination_zip(self, client):
        with pytest.raises(ValidationError, match="destination_zip"):
            client.prices.domestic("10001", "", 2.5)

    def test_domestic_requires_positive_weight(self, client):
        with pytest.raises(ValidationError, match="weight"):
            client.prices.domestic("10001", "90210", 0)

    def test_domestic_with_mail_class(self, client, mock_api):
        mock_api.post("/prices/v3/total-rates/search").mock(
            return_value=httpx.Response(200, json=DOMESTIC_RATES_RESPONSE)
        )
        result = client.prices.domestic("10001", "90210", 2.5, mail_class="PRIORITY_MAIL")
        assert result is not None

    def test_domestic_api_error(self, client, mock_api):
        mock_api.post("/prices/v3/total-rates/search").mock(
            return_value=httpx.Response(422, text="Invalid request")
        )
        with pytest.raises(APIError, match="422"):
            client.prices.domestic("10001", "90210", 2.5)


class TestInternationalPrices:
    """International rate quote tests."""

    def test_international_success(self, client, mock_api):
        mock_api.post("/international-prices/v3/total-rates/search").mock(
            return_value=httpx.Response(200, json=INTL_RATES_RESPONSE)
        )
        result = client.prices.international("10001", "CA", 3.0)
        assert "rates" in result
        assert result["input"]["destination"] == "CA"

    def test_international_requires_country_code(self, client):
        with pytest.raises(ValidationError, match="destination_country_code"):
            client.prices.international("10001", "", 3.0)

    def test_international_validates_country_code_length(self, client):
        with pytest.raises(ValidationError, match="2-letter"):
            client.prices.international("10001", "CAN", 3.0)

    def test_international_validates_mail_class(self, client):
        with pytest.raises(ValidationError, match="Invalid international"):
            client.prices.international("10001", "CA", 3.0, mail_class="FAKE_CLASS")

    def test_international_uppercases_country(self, client, mock_api):
        mock_api.post("/international-prices/v3/total-rates/search").mock(
            return_value=httpx.Response(200, json=INTL_RATES_RESPONSE)
        )
        result = client.prices.international("10001", "gb", 1.0)
        assert result["input"]["destination"] == "GB"
