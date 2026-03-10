"""USPS v3 Python SDK — direct integration with USPS Web Tools v3 REST API.

Usage:
    from usps_v3 import Client

    client = Client(client_id="...", client_secret="...")
    result = client.addresses.validate(street_address="1600 Pennsylvania Ave NW", city="Washington", state="DC")

Or with environment variables (USPS_CLIENT_ID, USPS_CLIENT_SECRET):
    client = Client()
"""

from .client import Client
from .exceptions import APIError, AuthError, NetworkError, RateLimitError, USPSError, ValidationError

# Alias for consistency with Node SDK (exports USPSClient)
USPSClient = Client

__version__ = "1.0.1"
__all__ = [
    "Client",
    "USPSClient",
    "USPSError",
    "AuthError",
    "ValidationError",
    "RateLimitError",
    "APIError",
    "NetworkError",
]
