"""Basic usage examples for BillionVerify Python SDK.

This example demonstrates:
- Single email verification using verify()
- Bulk email verification using verify_bulk() (sync, max 50 emails)
- Getting credits with get_credits()
- Health check with health_check()
"""

import os

from billionverify import (
    AuthenticationError,
    BillionVerify,
    InsufficientCreditsError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)

# Get API key from environment variable
API_KEY = os.getenv("BILLIONVERIFY_API_KEY", "your-api-key")


def single_email_verification():
    """Verify a single email address."""
    print("=" * 50)
    print("Single Email Verification")
    print("=" * 50)

    client = BillionVerify(api_key=API_KEY)

    try:
        # Verify a single email using the /verify/single endpoint
        result = client.verify(
            email="test@example.com",
            check_smtp=True,  # Optional: perform SMTP verification
        )

        # Access the flat response structure
        print(f"Email: {result.email}")
        print(f"Status: {result.status}")  # valid, invalid, unknown, risky, disposable, catchall, role
        print(f"Score: {result.score}")
        print(f"Is Deliverable: {result.is_deliverable}")
        print(f"Is Disposable: {result.is_disposable}")
        print(f"Is Catchall: {result.is_catchall}")
        print(f"Is Role: {result.is_role}")
        print(f"Is Free: {result.is_free}")
        print(f"Domain: {result.domain}")
        print(f"Reason: {result.reason}")
        print(f"SMTP Check: {result.check_smtp}")
        print(f"Credits Used: {result.credits_used}")

        if result.domain_suggestion:
            print(f"Domain Suggestion: {result.domain_suggestion}")

        if result.mx_records:
            print(f"MX Records: {', '.join(result.mx_records)}")

    except AuthenticationError:
        print("Error: Invalid API key")
    except ValidationError as e:
        print(f"Error: Invalid input - {e.message}")
    except TimeoutError:
        print("Error: Request timed out")

    finally:
        client.close()


def bulk_email_verification():
    """Verify multiple emails synchronously (max 50)."""
    print("\n" + "=" * 50)
    print("Bulk Email Verification (Synchronous)")
    print("=" * 50)

    # Using context manager for automatic cleanup
    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Verify multiple emails (max 50)
            emails = [
                "user1@example.com",
                "user2@example.com",
                "test@gmail.com",
                "info@company.com",
            ]

            # verify_bulk() returns BulkVerifyResponse directly
            response = client.verify_bulk(
                emails=emails,
                check_smtp=True,  # Optional
            )

            print(f"Total emails: {response.total_emails}")
            print(f"Credits used: {response.credits_used}")
            print("\nResults:")

            for result in response.results:
                print(f"\n  {result.email}:")
                print(f"    Status: {result.status}")
                print(f"    Score: {result.score}")
                print(f"    Deliverable: {result.is_deliverable}")
                print(f"    Disposable: {result.is_disposable}")
                print(f"    Catchall: {result.is_catchall}")
                print(f"    Role: {result.is_role}")
                print(f"    Domain: {result.domain}")

        except ValidationError as e:
            print(f"Error: {e.message}")
        except InsufficientCreditsError:
            print("Error: Not enough credits")


def get_credits_example():
    """Get current credit balance."""
    print("\n" + "=" * 50)
    print("Getting Credits")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            credits = client.get_credits()

            print(f"Account ID: {credits.account_id}")
            print(f"API Key: {credits.api_key_name} ({credits.api_key_id})")
            print(f"Credits Balance: {credits.credits_balance}")
            print(f"Credits Consumed: {credits.credits_consumed}")
            print(f"Credits Added: {credits.credits_added}")
            print(f"Last Updated: {credits.last_updated}")

        except AuthenticationError:
            print("Error: Invalid API key")


def health_check_example():
    """Check API health status."""
    print("\n" + "=" * 50)
    print("Health Check")
    print("=" * 50)

    # Health check doesn't require authentication, but we still need a client
    client = BillionVerify(api_key=API_KEY)

    try:
        health = client.health_check()
        print(f"Status: {health.status}")
        if health.version:
            print(f"Version: {health.version}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        client.close()


def error_handling_example():
    """Demonstrate error handling."""
    print("\n" + "=" * 50)
    print("Error Handling")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Try to verify with too many emails (will fail validation)
            emails = [f"user{i}@example.com" for i in range(60)]  # More than 50
            client.verify_bulk(emails)

        except ValidationError as e:
            print(f"ValidationError caught: {e.message}")

        try:
            # Try to verify an invalid email format
            client.verify("not-an-email")

        except ValidationError as e:
            print(f"ValidationError caught: {e.message}")

        except RateLimitError as e:
            print(f"RateLimitError caught: Retry after {e.retry_after} seconds")


if __name__ == "__main__":
    # Run all examples
    single_email_verification()
    bulk_email_verification()
    get_credits_example()
    health_check_example()
    error_handling_example()
