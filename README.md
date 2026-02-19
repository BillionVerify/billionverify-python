# billionverify

Official BillionVerify Python SDK for email verification.

**Documentation:** https://billionverify.com/docs

## Installation

```bash
pip install billionverify
```

## Quick Start

```python
from billionverify import BillionVerify

client = BillionVerify(api_key="your-api-key")

# Verify a single email
result = client.verify("user@example.com")
print(result.status)  # 'valid', 'invalid', 'unknown', 'risky', 'disposable', 'catchall', 'role'
print(result.is_deliverable)  # True or False
```

## Configuration

```python
client = BillionVerify(
    api_key="your-api-key",        # Required
    base_url="https://api.billionverify.com/v1",  # Optional
    timeout=30.0,                   # Optional: Request timeout in seconds (default: 30)
    retries=3,                      # Optional: Number of retries (default: 3)
)
```

## Single Email Verification

Uses the `/verify/single` endpoint:

```python
result = client.verify(
    email="user@example.com",
    check_smtp=True,  # Optional: Perform SMTP verification (default: True)
)

# Flat response structure
print(result.email)           # 'user@example.com'
print(result.status)          # 'valid', 'invalid', 'unknown', 'risky', 'disposable', 'catchall', 'role'
print(result.score)           # 0.95
print(result.is_deliverable)  # True
print(result.is_disposable)   # False
print(result.is_catchall)     # False
print(result.is_role)         # False
print(result.is_free)         # True
print(result.domain)          # 'example.com'
print(result.reason)          # 'Valid email address'
print(result.smtp_check)      # True (whether SMTP was performed)
print(result.credits_used)    # 1
```

## Bulk Email Verification (Synchronous)

Verify up to 50 emails synchronously using `verify_bulk()`:

```python
# Synchronous bulk verification (max 50 emails)
response = client.verify_bulk(
    emails=["user1@example.com", "user2@example.com", "user3@example.com"],
    check_smtp=True,  # Optional
)

# Returns BulkVerifyResponse directly
print(f"Total: {response.total}")
print(f"Credits used: {response.credits_used}")

for result in response.results:
    print(f"{result.email}: {result.status}")
    print(f"  Deliverable: {result.is_deliverable}")
    print(f"  Disposable: {result.is_disposable}")
    print(f"  Catchall: {result.is_catchall}")
    print(f"  Role: {result.is_role}")
```

## File Upload (Async Verification)

For large lists, use `upload_file()` for asynchronous file verification:

```python
# Upload a file for async verification
job = client.upload_file(
    file_path="emails.csv",
    check_smtp=True,
    email_column="email",        # Column name for CSV files
    preserve_original=True,      # Keep original columns in results
)

print(f"Job ID: {job.job_id}")
print(f"Status: {job.status}")

# Get job status (with optional long-polling)
status = client.get_file_job_status(
    job_id=job.job_id,
    timeout=60,  # Long-poll for up to 60 seconds (0-300)
)
print(f"Progress: {status.progress_percent}%")

# Wait for completion (polling)
completed = client.wait_for_file_job(
    job_id=job.job_id,
    poll_interval=5.0,  # seconds
    max_wait=600.0,     # seconds
)

# Get results with filter options
results = client.get_file_job_results(
    job_id=job.job_id,
    limit=100,
    offset=0,
    valid=True,       # Include valid emails
    invalid=True,     # Include invalid emails
    unknown=True,     # Include unknown emails
    risky=True,       # Include risky emails
    disposable=True,  # Include disposable emails
    catchall=True,    # Include catch-all emails
    role=True,        # Include role-based emails
)

for item in results.results:
    print(f"{item.email}: {item.status}")
```

## Async Support

```python
import asyncio
from billionverify import AsyncBillionVerify

async def main():
    async with AsyncBillionVerify(api_key="your-api-key") as client:
        # Single verification
        result = await client.verify("user@example.com")
        print(result.status)

        # Bulk verification
        response = await client.verify_bulk([
            "user1@example.com",
            "user2@example.com"
        ])
        for r in response.results:
            print(f"{r.email}: {r.status}")

asyncio.run(main())
```

## Health Check

Check API health status (no authentication required):

```python
health = client.health_check()
print(health.status)   # 'ok'
print(health.version)  # API version
```

## Credits

```python
credits = client.get_credits()
print(credits.credits_balance)   # Available credits
print(credits.credits_consumed)  # Credits used
print(credits.credits_added)     # Total credits added
print(credits.api_key_name)      # API key name
```

## Webhooks

Webhooks support events: `file.completed`, `file.failed`

```python
# Create a webhook
webhook = client.create_webhook(
    url="https://your-app.com/webhooks/billionverify",
    events=["file.completed", "file.failed"],
)
print(f"Webhook ID: {webhook.id}")
print(f"Secret: {webhook.secret}")  # Save this for signature verification

# List webhooks
webhooks = client.list_webhooks()
for wh in webhooks:
    print(f"{wh.id}: {wh.url}")

# Delete a webhook
client.delete_webhook(webhook.id)

# Verify webhook signature
from billionverify import BillionVerify

is_valid = BillionVerify.verify_webhook_signature(
    payload=raw_body,
    signature=signature_header,
    secret="your-webhook-secret",
)
```

## Error Handling

```python
from billionverify import (
    BillionVerify,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    InsufficientCreditsError,
    NotFoundError,
    TimeoutError,
)

try:
    result = client.verify("user@example.com")
except AuthenticationError:
    print("Invalid API key")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except ValidationError as e:
    print(f"Invalid input: {e.message}")
except InsufficientCreditsError:
    print("Not enough credits")
except NotFoundError:
    print("Resource not found")
except TimeoutError:
    print("Request timed out")
```

## Context Manager

```python
with BillionVerify(api_key="your-api-key") as client:
    result = client.verify("user@example.com")
    print(result.status)
# Connection is automatically closed
```

## Type Hints

This SDK includes full type annotations for IDE support and type checking.

```python
from billionverify import (
    VerificationResult,
    BulkVerifyResponse,
    FileJobResponse,
    CreditsResponse,
    VerificationStatus,
)

def process_result(result: VerificationResult) -> None:
    if result.status == "valid":
        print(f"Email {result.email} is valid")

    if result.is_deliverable and not result.is_disposable:
        print("Safe to send to this email")
```

## Status Values

The verification status can be one of:

- `valid` - Email is valid and deliverable
- `invalid` - Email is invalid or does not exist
- `unknown` - Could not determine status
- `risky` - Email exists but may have delivery issues
- `disposable` - Temporary/disposable email address
- `catchall` - Domain accepts all emails (catch-all)
- `role` - Role-based email (e.g., info@, support@)

## License

MIT
