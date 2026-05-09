"""Async bulk verification example for BillionVerify Python SDK.

This example demonstrates:
- Submitting a 51-1000 email batch via verify_bulk_async()
- Polling task status with get_bulk_task_status()
- Downloading results as CSV with download_bulk_results()
"""

import asyncio
import os

from billionverify import (
    AsyncBillionVerify,
    BillionVerify,
    NotFoundError,
    ValidationError,
)

# Get API key from environment variable
API_KEY = os.getenv("BILLIONVERIFY_API_KEY", "your-api-key")

# Sample batch — between 51 and 1000 emails
SAMPLE_EMAILS = [f"user{i}@example.com" for i in range(1, 101)]


# ---------------------------------------------------------------------------
# Async workflow
# ---------------------------------------------------------------------------

async def async_bulk_workflow():
    """Submit, poll, and download a bulk async task using the async client."""
    print("=" * 55)
    print("Async Bulk Verification Workflow (AsyncBillionVerify)")
    print("=" * 55)

    async with AsyncBillionVerify(api_key=API_KEY) as client:
        # Step 1: Submit the batch
        print(f"\nStep 1: Submitting {len(SAMPLE_EMAILS)} emails...")
        try:
            task = await client.verify_bulk_async(SAMPLE_EMAILS, check_smtp=True)
        except ValidationError as e:
            print(f"Validation error: {e.message}")
            return

        print(f"Task submitted successfully!")
        print(f"  Task ID:         {task.task_id}")
        print(f"  Status:          {task.status}")
        print(f"  Estimated count: {task.estimated_count}")
        print(f"  Status URL:      {task.status_url}")
        print(f"  Created at:      {task.created_at}")

        # Step 2: Poll until completed (simple polling loop)
        print(f"\nStep 2: Polling task status...")
        for attempt in range(1, 61):
            status = await client.get_bulk_task_status(task.task_id)
            print(f"  [{attempt:02d}] status={status.status}  progress={status.progress}%"
                  f"  processed={status.processed_emails}/{status.total_emails}")

            if status.status in ("completed", "failed"):
                break

            await asyncio.sleep(5)
        else:
            print("Timed out waiting for task completion.")
            return

        if status.status == "failed":
            print(f"Task failed: {status.error_message}")
            return

        print(f"\nTask completed!")
        print(f"  Valid:       {status.valid_emails}")
        print(f"  Invalid:     {status.invalid_emails}")
        print(f"  Unknown:     {status.unknown_emails}")
        print(f"  Catchall:    {status.catchall_emails}")
        print(f"  Disposable:  {status.disposable_emails}")
        print(f"  Risky:       {status.risky_emails}")
        print(f"  Credits used:{status.credits_used}")

        # Step 3: Download results
        print(f"\nStep 3: Downloading results...")
        try:
            output = await client.download_bulk_results(
                task_id=task.task_id,
                output_path="bulk_async_results.csv",
            )
            print(f"All results saved to: {output}")

            # Download only valid emails
            output_valid = await client.download_bulk_results(
                task_id=task.task_id,
                output_path="bulk_async_results_valid.csv",
                valid=True,
            )
            print(f"Valid-only results saved to: {output_valid}")

        except NotFoundError:
            print(f"Task not found: {task.task_id}")
        except ValidationError as e:
            print(f"Validation error: {e.message}")


# ---------------------------------------------------------------------------
# Sync workflow
# ---------------------------------------------------------------------------

def sync_bulk_workflow():
    """Submit, poll, and download a bulk async task using the sync client."""
    import time

    print("=" * 55)
    print("Async Bulk Verification Workflow (BillionVerify sync)")
    print("=" * 55)

    with BillionVerify(api_key=API_KEY) as client:
        # Step 1: Submit the batch
        print(f"\nStep 1: Submitting {len(SAMPLE_EMAILS)} emails...")
        try:
            task = client.verify_bulk_async(SAMPLE_EMAILS, check_smtp=True)
        except ValidationError as e:
            print(f"Validation error: {e.message}")
            return

        print(f"Task submitted successfully!")
        print(f"  Task ID:         {task.task_id}")
        print(f"  Status:          {task.status}")
        print(f"  Estimated count: {task.estimated_count}")
        print(f"  Status URL:      {task.status_url}")

        # Step 2: Poll until completed
        print(f"\nStep 2: Polling task status...")
        for attempt in range(1, 61):
            status = client.get_bulk_task_status(task.task_id)
            print(f"  [{attempt:02d}] status={status.status}  progress={status.progress}%"
                  f"  processed={status.processed_emails}/{status.total_emails}")

            if status.status in ("completed", "failed"):
                break

            time.sleep(5)
        else:
            print("Timed out waiting for task completion.")
            return

        if status.status == "failed":
            print(f"Task failed: {status.error_message}")
            return

        print(f"\nTask completed! Credits used: {status.credits_used}")

        # Step 3: Download results
        print(f"\nStep 3: Downloading results...")
        try:
            output = client.download_bulk_results(
                task_id=task.task_id,
                output_path="bulk_async_results_sync.csv",
            )
            print(f"Results saved to: {output}")
        except NotFoundError:
            print(f"Task not found: {task.task_id}")
        except ValidationError as e:
            print(f"Validation error: {e.message}")


if __name__ == "__main__":
    # Run async workflow (default)
    asyncio.run(async_bulk_workflow())

    # To use the sync client instead, uncomment:
    # sync_bulk_workflow()
