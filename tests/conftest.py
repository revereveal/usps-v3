"""Shared test fixtures for USPS v3 SDK tests."""

import time

import httpx
import pytest
import respx

# Test credentials
TEST_CLIENT_ID = "test-client-id"
TEST_CLIENT_SECRET = "test-client-secret"
TEST_BASE_URL = "https://apis.usps.com"

# Reusable OAuth response
OAUTH_RESPONSE = {
    "access_token": "test-oauth-token-abc123",
    "token_type": "Bearer",
    "expires_in": 28800,
    "scope": "addresses tracking prices labels",
    "issued_at": str(int(time.time() * 1000)),
}

# Payment Auth response
PAYMENT_AUTH_RESPONSE = {
    "paymentAuthorizationToken": "test-payment-token-xyz789",
    "expiresIn": 28800,
}


@pytest.fixture
def mock_api():
    """respx mock router for USPS API."""
    with respx.mock(base_url=TEST_BASE_URL, assert_all_called=False) as router:
        # Always mock the OAuth endpoint
        router.post("/oauth2/v3/token").mock(
            return_value=httpx.Response(200, json=OAUTH_RESPONSE)
        )
        yield router


@pytest.fixture
def mock_api_with_payment(mock_api):
    """Mock API with both OAuth and Payment Auth."""
    mock_api.post("/payments/v3/payment-authorization").mock(
        return_value=httpx.Response(200, json=PAYMENT_AUTH_RESPONSE)
    )
    return mock_api


@pytest.fixture
def tmp_cache(tmp_path):
    """Temporary cache directory for token persistence tests."""
    return tmp_path / ".usps-v3"


@pytest.fixture
def client(mock_api, tmp_cache):
    """Pre-configured USPS client with mocked API."""
    from usps_v3 import Client

    c = Client(
        client_id=TEST_CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET,
        cache_dir=tmp_cache,
    )
    yield c
    c.close()


@pytest.fixture
def client_with_payment(mock_api_with_payment, tmp_cache):
    """Pre-configured client with Payment Auth credentials."""
    from usps_v3 import Client

    c = Client(
        client_id=TEST_CLIENT_ID,
        client_secret=TEST_CLIENT_SECRET,
        cache_dir=tmp_cache,
        crid="56982563",
        master_mid="904128936",
        label_mid="904128937",
        epa_account="1000405525",
    )
    yield c
    c.close()
