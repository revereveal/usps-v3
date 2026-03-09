"""Tests for the main Client class."""

import os
from unittest.mock import patch

import pytest

from usps_v3 import Client


class TestClientInit:
    """Client initialization and credential resolution."""

    def test_requires_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="USPS credentials required"):
                Client()

    def test_accepts_explicit_credentials(self, mock_api, tmp_cache):
        c = Client(client_id="id", client_secret="secret", cache_dir=tmp_cache)
        assert repr(c) == "<usps_v3.Client base_url='https://apis.usps.com'>"
        c.close()

    def test_reads_env_vars(self, mock_api, tmp_cache):
        with patch.dict(os.environ, {"USPS_CLIENT_ID": "env-id", "USPS_CLIENT_SECRET": "env-secret"}):
            c = Client(cache_dir=tmp_cache)
            assert c is not None
            c.close()

    def test_context_manager(self, mock_api, tmp_cache):
        with Client(client_id="id", client_secret="secret", cache_dir=tmp_cache) as c:
            assert c is not None

    def test_custom_base_url(self, tmp_cache):
        import respx
        import httpx

        with respx.mock(base_url="https://apis-tem.usps.com", assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "tem-token",
                    "expires_in": 28800,
                })
            )
            c = Client(
                client_id="id",
                client_secret="secret",
                base_url="https://apis-tem.usps.com",
                cache_dir=tmp_cache,
            )
            assert "apis-tem" in repr(c)
            c.close()


class TestClientAPIs:
    """Verify all API modules are accessible."""

    def test_has_addresses(self, client):
        assert hasattr(client, "addresses")

    def test_has_tracking(self, client):
        assert hasattr(client, "tracking")

    def test_has_labels(self, client):
        assert hasattr(client, "labels")

    def test_has_prices(self, client):
        assert hasattr(client, "prices")

    def test_has_standards(self, client):
        assert hasattr(client, "standards")

    def test_has_locations(self, client):
        assert hasattr(client, "locations")

    def test_token_status(self, client):
        status = client.token_status
        assert "oauth" in status
        assert "payment" in status


class TestClientRefresh:
    """Token refresh behavior."""

    def test_refresh_tokens(self, client_with_payment):
        result = client_with_payment.refresh_tokens()
        assert result["oauth"] is True
        assert result["payment"] is True
