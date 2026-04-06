"""Async example for BillionVerify Python SDK.

This example demonstrates async/await usage with the AsyncBillionVerify client:
- Async single email verification
- Async bulk verification
- Async file upload and monitoring
- Concurrent verification of multiple emails
- Async context manager usage
"""

import asyncio
import os
import tempfile
from typing import List

from billionverify import (
    AsyncBillionVerify,
    AuthenticationError,
    TimeoutError,
    ValidationError,
    VerificationResult,
)

# Get API key from environment variable
API_KEY = os.getenv("BILLIONVERIFY_API_KEY", "your-api-key")


async def single_verification_example():
    """Async single email verification."""
    print("=" * 50)
    print("Async Single Email Verification")
    print("=" * 50)

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        try:
            # Verify a single email
            result = await client.verify(
                email="test@example.com",
                check_smtp=True,
            )

            print(f"Email: {result.email}")
            print(f"Status: {result.status}")
            print(f"Score: {result.score}")
            print(f"Deliverable: {result.is_deliverable}")
            print(f"Disposable: {result.is_disposable}")
            print(f"Catchall: {result.is_catchall}")
            print(f"Role: {result.is_role}")
            print(f"Domain: {result.domain}")
            print(f"Reason: {result.reason}")
            print(f"SMTP Check: {result.check_smtp}")

        except AuthenticationError:
            print("Error: Invalid API key")
        except ValidationError as e:
            print(f"Validation error: {e.message}")


async def bulk_verification_example():
    """Async bulk email verification (max 50 emails)."""
    print("\n" + "=" * 50)
    print("Async Bulk Email Verification")
    print("=" * 50)

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        try:
            emails = [
                "user1@example.com",
                "user2@example.com",
                "test@gmail.com",
                "info@company.com",
            ]

            # Verify multiple emails (max 50)
            response = await client.verify_bulk(
                emails=emails,
                check_smtp=True,
            )

            print(f"Total: {response.total_emails}")
            print(f"Credits used: {response.credits_used}")

            for result in response.results:
                print(f"\n  {result.email}:")
                print(f"    Status: {result.status}")
                print(f"    Deliverable: {result.is_deliverable}")

        except ValidationError as e:
            print(f"Validation error: {e.message}")


async def concurrent_verification_example():
    """Verify multiple emails concurrently."""
    print("\n" + "=" * 50)
    print("Concurrent Email Verification")
    print("=" * 50)

    emails = [
        "user1@example.com",
        "user2@example.com",
        "test@gmail.com",
        "info@company.com",
        "support@business.com",
    ]

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        try:
            # Create verification tasks for all emails
            tasks = [
                client.verify(email, check_smtp=True)
                for email in emails
            ]

            # Run all verifications concurrently
            print(f"Verifying {len(emails)} emails concurrently...")
            results: List[VerificationResult] = await asyncio.gather(
                *tasks,
                return_exceptions=True,  # Don't fail all if one fails
            )

            # Process results
            for result in results:
                if isinstance(result, Exception):
                    print(f"Error: {result}")
                else:
                    print(f"{result.email}: {result.status} (score: {result.score})")

        except Exception as e:
            print(f"Error: {e}")


async def file_upload_example():
    """Async file upload and monitoring."""
    print("\n" + "=" * 50)
    print("Async File Upload")
    print("=" * 50)

    # Create a sample CSV file
    csv_content = """email
user1@example.com
user2@example.com
test@gmail.com
"""
    fd, csv_path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as f:
        f.write(csv_content)

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        try:
            # Upload the file
            print("Uploading file...")
            task = await client.upload_file(
                file_path=csv_path,
                check_smtp=True,
                email_column="email",
            )
            print(f"Task ID: {task.task_id}")
            print(f"Status: {task.status}")
            print(f"Estimated count: {task.estimated_count}")

            # Wait for completion
            print("\nWaiting for completion...")
            completed = await client.wait_for_file_task(
                task_id=task.task_id,
                poll_interval=2.0,
                max_wait=300.0,
            )
            print(f"Final status: {completed.status}")
            print(f"Valid: {completed.valid_emails}")
            print(f"Invalid: {completed.invalid_emails}")

            # Download results as CSV
            if completed.status == "completed":
                output = await client.download_file_results(
                    task_id=task.task_id,
                    output_path="async_results.csv",
                )
                print(f"\nResults saved to: {output}")

        except TimeoutError as e:
            print(f"Timeout: {e}")
        except ValidationError as e:
            print(f"Validation error: {e.message}")
        finally:
            os.unlink(csv_path)


async def credits_and_health_example():
    """Async credits and health check."""
    print("\n" + "=" * 50)
    print("Async Credits and Health Check")
    print("=" * 50)

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        # Run both requests concurrently
        health_task = client.health_check()
        credits_task = client.get_credits()

        health, credits = await asyncio.gather(
            health_task,
            credits_task,
            return_exceptions=True,
        )

        if not isinstance(health, Exception):
            print(f"Health status: {health.status}")
            if health.version:
                print(f"API version: {health.version}")

        if not isinstance(credits, Exception):
            print(f"Credits balance: {credits.credits_balance}")
            print(f"Credits consumed: {credits.credits_consumed}")


async def webhook_management_example():
    """Async webhook management."""
    print("\n" + "=" * 50)
    print("Async Webhook Management")
    print("=" * 50)

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        try:
            # List existing webhooks
            webhooks = await client.list_webhooks()
            print(f"Existing webhooks: {len(webhooks)}")

            # Create a new webhook
            webhook = await client.create_webhook(
                url="https://example.com/webhook",
                events=["file.completed", "file.failed"],
            )
            print(f"\nCreated webhook: {webhook.id}")
            print(f"Secret: {webhook.secret}")

            # Delete the webhook
            await client.delete_webhook(webhook.id)
            print(f"Deleted webhook: {webhook.id}")

        except ValidationError as e:
            print(f"Validation error: {e.message}")
        except Exception as e:
            print(f"Error: {e}")


async def batch_processing_example():
    """Process emails in batches with rate limiting."""
    print("\n" + "=" * 50)
    print("Batch Processing with Rate Limiting")
    print("=" * 50)

    # Large list of emails to process
    all_emails = [f"user{i}@example.com" for i in range(100)]

    # Process in batches of 50 (max for verify_bulk)
    batch_size = 50
    delay_between_batches = 1.0  # seconds

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        all_results = []

        for i in range(0, len(all_emails), batch_size):
            batch = all_emails[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(all_emails) + batch_size - 1) // batch_size

            print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} emails)...")

            try:
                response = await client.verify_bulk(batch)
                all_results.extend(response.results)

                # Summary for this batch
                valid = sum(1 for r in response.results if r.status == "valid")
                invalid = sum(1 for r in response.results if r.status == "invalid")
                print(f"  Valid: {valid}, Invalid: {invalid}")

            except Exception as e:
                print(f"  Error processing batch: {e}")

            # Delay between batches to avoid rate limiting
            if i + batch_size < len(all_emails):
                await asyncio.sleep(delay_between_batches)

        # Final summary
        print(f"\nTotal processed: {len(all_results)}")
        print(f"Total valid: {sum(1 for r in all_results if r.status == 'valid')}")
        print(f"Total invalid: {sum(1 for r in all_results if r.status == 'invalid')}")


async def main():
    """Run all async examples."""
    await single_verification_example()
    await bulk_verification_example()
    await concurrent_verification_example()
    await credits_and_health_example()

    # Uncomment to run additional examples
    # await file_upload_example()
    # await webhook_management_example()
    # await batch_processing_example()


if __name__ == "__main__":
    asyncio.run(main())
