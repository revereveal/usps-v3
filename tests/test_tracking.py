"""Tests for package tracking."""

import httpx
import pytest

from usps_v3.exceptions import APIError, RateLimitError, ValidationError


TRACKING_RESPONSE = {
    "trackingNumber": "9400111899223033005282",
    "statusCategory": "Delivered",
    "statusSummary": "Your item was delivered on March 9, 2026",
    "trackingEvents": [
        {
            "eventType": "Delivered",
            "eventCode": "01",
            "eventCity": "NEW YORK",
            "eventState": "NY",
            "eventZIP": "10001",
            "eventTimestamp": "2026-03-09T14:30:00Z",
        },
        {
            "eventType": "Out for Delivery",
            "eventCode": "OF",
            "eventCity": "NEW YORK",
            "eventState": "NY",
            "eventZIP": "10001",
            "eventTimestamp": "2026-03-09T06:15:00Z",
        },
    ],
}


class TestTrack:
    """Package tracking tests."""

    def test_track_success(self, client, mock_api):
        mock_api.get("/tracking/v3/tracking/9400111899223033005282").mock(
            return_value=httpx.Response(200, json=TRACKING_RESPONSE)
        )
        result = client.tracking.track("9400111899223033005282")
        assert result["statusCategory"] == "Delivered"
        assert len(result["trackingEvents"]) == 2

    def test_track_requires_number(self, client):
        with pytest.raises(ValidationError, match="tracking_number"):
            client.tracking.track("")

    def test_track_strips_whitespace(self, client, mock_api):
        mock_api.get("/tracking/v3/tracking/9400111899223033005282").mock(
            return_value=httpx.Response(200, json=TRACKING_RESPONSE)
        )
        result = client.tracking.track("  9400111899223033005282  ")
        assert result["trackingNumber"] == "9400111899223033005282"

    def test_track_summary_expand(self, client, mock_api):
        summary_response = {"statusCategory": "In Transit", "statusSummary": "In transit"}
        mock_api.get("/tracking/v3/tracking/TEST123").mock(
            return_value=httpx.Response(200, json=summary_response)
        )
        result = client.tracking.track("TEST123", expand="SUMMARY")
        assert result["statusCategory"] == "In Transit"

    def test_track_not_found(self, client, mock_api):
        mock_api.get("/tracking/v3/tracking/INVALID").mock(
            return_value=httpx.Response(404, text="Tracking number not found")
        )
        with pytest.raises(APIError, match="404"):
            client.tracking.track("INVALID")

    def test_track_rate_limit(self, client, mock_api):
        mock_api.get("/tracking/v3/tracking/RATELIMITED").mock(
            return_value=httpx.Response(429)
        )
        with pytest.raises(RateLimitError):
            client.tracking.track("RATELIMITED")
