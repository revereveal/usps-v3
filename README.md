# usps-v3

Python SDK for the **USPS Web Tools v3 REST API** — the replacement for the retired XML-based Web Tools.

Direct USPS integration. OAuth 2.0. No middleman. No per-label fees.

## Install

```bash
pip install usps-v3
```

## Quick Start

```python
from usps_v3 import Client

# Credentials from USPS Business Customer Gateway
client = Client(client_id="your-id", client_secret="your-secret")
# Or set USPS_CLIENT_ID and USPS_CLIENT_SECRET environment variables:
# client = Client()

# Validate an address (FREE)
result = client.addresses.validate(
    street_address="1600 Pennsylvania Ave NW",
    city="Washington",
    state="DC",
    zip_code="20500",
)
print(result["address"]["ZIPPlus4"])  # "0005"

# Track a package (FREE)
info = client.tracking.track("9400111899223033005282")
print(info["statusCategory"])  # "Delivered"

# Get delivery time estimates (FREE)
standards = client.standards.estimates("10001", "90210")

# Find drop-off locations (FREE)
locations = client.locations.dropoff("20500", mail_class="PRIORITY_MAIL")

# Get rate quotes
rates = client.prices.domestic("10001", "90210", weight=2.5)
print(rates["rates"]["rateOptions"][0]["totalPrice"])

# International rates
intl = client.prices.international("10001", "CA", weight=3.0)

# Create shipping labels (requires USPS enrollment + COP claims)
label = client.labels.create(
    from_address={"streetAddress": "123 Sender St", "city": "New York", "state": "NY", "ZIPCode": "10001"},
    to_address={"streetAddress": "456 Recipient Ave", "city": "LA", "state": "CA", "ZIPCode": "90001"},
    mail_class="PRIORITY_MAIL",
    weight=2.0,
)
print(label["trackingNumber"])

# Void a label
client.labels.void("9400111899223033005282")
```

## Features

| Feature | Endpoint | Auth Required |
|---------|----------|--------------|
| Address Validation | `addresses.validate()` | OAuth only |
| City/State Lookup | `addresses.city_state()` | OAuth only |
| Package Tracking | `tracking.track()` | OAuth only |
| Service Standards | `standards.estimates()` | OAuth only |
| Drop-off Locations | `locations.dropoff()` | OAuth only |
| Domestic Prices | `prices.domestic()` | OAuth only |
| International Prices | `prices.international()` | OAuth only |
| Label Creation | `labels.create()` | OAuth + Payment Auth |
| Label Void | `labels.void()` | OAuth only |

## Authentication

The SDK handles OAuth 2.0 token lifecycle automatically:

- **Token caching**: Tokens are cached in memory and on disk (`~/.usps-v3/tokens.json`)
- **Auto-refresh**: Tokens refresh automatically 30 minutes before expiry
- **Thread-safe**: Safe for concurrent use across threads

### Getting Credentials

1. Register at [USPS Business Customer Gateway](https://gateway.usps.com)
2. Create an application in the API developer portal
3. Note your `client_id` and `client_secret`

For label creation, you also need:
- **CRID** (Customer Registration ID)
- **MIDs** (Mailer IDs — master + label owner)
- **EPA** (Enterprise Payment Account)
- **COP claims linking** at [cop.usps.com](https://cop.usps.com)

```python
client = Client(
    client_id="...",
    client_secret="...",
    crid="56982563",
    master_mid="904128936",
    label_mid="904128937",
    epa_account="1000405525",
)
```

## Error Handling

```python
from usps_v3 import Client, AuthError, ValidationError, RateLimitError, APIError

try:
    result = client.addresses.validate(street_address="123 Main St")
except ValidationError as e:
    print(f"Bad input: {e} (field: {e.field})")
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except AuthError as e:
    print(f"Auth failed: {e}")
except APIError as e:
    print(f"USPS error ({e.status_code}): {e}")
```

## USPS Rate Limits

The v3 API defaults to **60 requests/hour** (down from unlimited in Web Tools). The SDK does not enforce this limit — USPS returns 429 when exceeded.

To request a higher limit, contact USPS at [emailus.usps.com](https://emailus.usps.com).

## Migration from Web Tools

If you're migrating from the retired USPS Web Tools XML API:

| Web Tools (XML) | v3 SDK (Python) |
|-----------------|-----------------|
| `<AddressValidateRequest>` | `client.addresses.validate(...)` |
| `<CityStateLookupRequest>` | `client.addresses.city_state(...)` |
| `<TrackFieldRequest>` | `client.tracking.track(...)` |
| `<RateV4Request>` | `client.prices.domestic(...)` |
| User ID auth | OAuth 2.0 (automatic) |
| XML response parsing | Python dicts (automatic) |
| Unlimited requests | 60/hr default (request increase) |

## Development

```bash
git clone https://github.com/revereveal/usps-v3.git
cd usps-v3
pip install -e ".[dev]"
pytest -v
```

## License

MIT — see [LICENSE](LICENSE).

Built by [RevAddress](https://revaddress.com) — direct USPS API integration for developers.
