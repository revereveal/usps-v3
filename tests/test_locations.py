"""Tests for drop-off location search."""

import httpx
import pytest

from usps_v3.exceptions import APIError, ValidationError


LOCATIONS_RESPONSE = {
    "dropoffLocations": [
        {
            "locationName": "WASHINGTON DC POST OFFICE",
            "locationType": "POST OFFICE",
            "address": {
                "streetAddress": "900 BRENTWOOD RD NE",
                "city": "WASHINGTON",
                "state": "DC",
                "ZIPCode": "20018",
            },
            "hours": "M-F 8:00AM-5:00PM",
        },
        {
            "locationName": "COLLECTION BOX",
            "locationType": "COLLECTION BOX",
            "address": {
                "streetAddress": "1600 PENNSYLVANIA AVE NW",
                "city": "WASHINGTON",
                "state": "DC",
                "ZIPCode": "20500",
            },
        },
    ],
}


class TestDropoff:
    """Drop-off location search tests."""

    def test_dropoff_success(self, client, mock_api):
        mock_api.get("/locations/v3/dropoff-locations").mock(
            return_value=httpx.Response(200, json=LOCATIONS_RESPONSE)
        )
        result = client.locations.dropoff("20500")
        assert "dropoffLocations" in result
        assert len(result["dropoffLocations"]) == 2

    def test_dropoff_with_mail_class(self, client, mock_api):
        mock_api.get("/locations/v3/dropoff-locations").mock(
            return_value=httpx.Response(200, json=LOCATIONS_RESPONSE)
        )
        result = client.locations.dropoff("20500", mail_class="PRIORITY_MAIL")
        assert result is not None

    def test_dropoff_with_dimensions(self, client, mock_api):
        mock_api.get("/locations/v3/dropoff-locations").mock(
            return_value=httpx.Response(200, json=LOCATIONS_RESPONSE)
        )
        result = client.locations.dropoff(
            "20500",
            origin_zip="10001",
            weight=5.0,
            length=12,
            width=9,
            height=4,
        )
        assert result is not None

    def test_dropoff_requires_zip(self, client):
        with pytest.raises(ValidationError, match="destination_zip"):
            client.locations.dropoff("")

    def test_dropoff_api_error(self, client, mock_api):
        mock_api.get("/locations/v3/dropoff-locations").mock(
            return_value=httpx.Response(400, text="Bad request")
        )
        with pytest.raises(APIError, match="400"):
            client.locations.dropoff("00000")
