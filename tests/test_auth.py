"""Tests for OAuth token management."""

import json
import time
from pathlib import Path

import httpx
import pytest
import respx

from usps_v3.auth import TokenManager
from usps_v3.exceptions import AuthError

BASE_URL = "https://apis.usps.com"


class TestOAuth:
    """OAuth bearer token lifecycle."""

    def test_fetches_token_on_first_call(self, tmp_path):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "fresh-token",
                    "expires_in": 28800,
                    "scope": "addresses",
                })
            )
            tm = TokenManager("id", "secret", cache_dir=tmp_path / "a")
            token = tm.get_oauth_token()
            assert token == "fresh-token"
            tm.close()

    def test_caches_token_in_memory(self, tmp_path):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            route = router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "cached-token",
                    "expires_in": 28800,
                })
            )
            tm = TokenManager("id", "secret", cache_dir=tmp_path / "b")
            tm.get_oauth_token()
            tm.get_oauth_token()  # Should use cached
            assert route.call_count == 1
            tm.close()

    def test_raises_on_401(self, tmp_path):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(401, text="invalid_client")
            )
            tm = TokenManager("bad-id", "bad-secret", cache_dir=tmp_path / "c")
            with pytest.raises(AuthError, match="401"):
                tm.get_oauth_token()
            tm.close()

    def test_persists_to_file(self, tmp_path):
        cache_dir = tmp_path / "d"
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "persisted-token",
                    "expires_in": 28800,
                })
            )
            tm = TokenManager("id", "secret", cache_dir=cache_dir)
            tm.get_oauth_token()

            cache_file = cache_dir / "tokens.json"
            assert cache_file.exists()
            data = json.loads(cache_file.read_text())
            assert data["oauth_token"] == "persisted-token"
            tm.close()

    def test_hydrates_from_cache(self, tmp_path):
        cache_dir = tmp_path / "e"
        cache_dir.mkdir()
        cache_file = cache_dir / "tokens.json"
        cache_file.write_text(json.dumps({
            "oauth_token": "cached-from-file",
            "oauth_expires_at": time.time() + 3600,
            "oauth_scope": "all",
            "payment_token": None,
            "payment_expires_at": 0,
        }))

        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            route = router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "should-not-be-used",
                    "expires_in": 28800,
                })
            )
            tm = TokenManager("id", "secret", cache_dir=cache_dir)
            token = tm.get_oauth_token()
            assert token == "cached-from-file"
            assert route.call_count == 0  # Should NOT have called USPS
            tm.close()


class TestPaymentAuth:
    """Payment Authorization token lifecycle."""

    def test_requires_enrollment_credentials(self, tmp_path):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "oauth-ok",
                    "expires_in": 28800,
                })
            )
            tm = TokenManager("id", "secret", cache_dir=tmp_path / "f")
            with pytest.raises(AuthError, match="requires crid"):
                tm.get_payment_token()
            tm.close()

    def test_fetches_payment_token(self, tmp_path):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "oauth-ok",
                    "expires_in": 28800,
                })
            )
            router.post("/payments/v3/payment-authorization").mock(
                return_value=httpx.Response(200, json={
                    "paymentAuthorizationToken": "pay-token-123",
                    "expiresIn": 28800,
                })
            )
            tm = TokenManager(
                "id", "secret",
                cache_dir=tmp_path / "g",
                crid="123", master_mid="456", label_mid="789", epa_account="000",
            )
            token = tm.get_payment_token()
            assert token == "pay-token-123"
            tm.close()

    def test_both_tokens(self, tmp_path):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "oauth-both",
                    "expires_in": 28800,
                })
            )
            router.post("/payments/v3/payment-authorization").mock(
                return_value=httpx.Response(200, json={
                    "paymentAuthorizationToken": "pay-both",
                    "expiresIn": 28800,
                })
            )
            tm = TokenManager(
                "id", "secret",
                cache_dir=tmp_path / "h",
                crid="123", master_mid="456", label_mid="789", epa_account="000",
            )
            oauth, payment = tm.get_both_tokens()
            assert oauth == "oauth-both"
            assert payment == "pay-both"
            tm.close()


class TestTokenStatus:
    """Token status reporting."""

    def test_status_structure(self, tmp_path):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
            router.post("/oauth2/v3/token").mock(
                return_value=httpx.Response(200, json={
                    "access_token": "status-token",
                    "expires_in": 28800,
                })
            )
            tm = TokenManager("id", "secret", cache_dir=tmp_path / "i")
            status = tm.status
            assert "oauth" in status
            assert "payment" in status
            assert "valid" in status["oauth"]
            assert "ttl_seconds" in status["oauth"]
            tm.close()
