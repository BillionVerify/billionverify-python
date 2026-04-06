"""File upload example for BillionVerify Python SDK.

This example demonstrates:
- File upload using upload_file() for async verification
- Getting task status with get_file_task_status() (with timeout for long-polling)
- Downloading results as CSV with download_file_results() with filter options
- Waiting for task completion using wait_for_file_task()
"""

import os
import tempfile

from billionverify import (
    BillionVerify,
    NotFoundError,
    TimeoutError,
    ValidationError,
)

# Get API key from environment variable
API_KEY = os.getenv("BILLIONVERIFY_API_KEY", "your-api-key")


def create_sample_csv() -> str:
    """Create a sample CSV file for testing."""
    csv_content = """email,name,company
user1@example.com,John Doe,Acme Inc
user2@example.com,Jane Smith,Tech Corp
test@gmail.com,Test User,Startup LLC
info@company.com,Info Contact,Company
support@business.com,Support Team,Business Ltd
"""
    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as f:
        f.write(csv_content)
    return path


def upload_file_example():
    """Upload a file for async verification."""
    print("=" * 50)
    print("File Upload for Async Verification")
    print("=" * 50)

    # Create a sample CSV file
    csv_path = create_sample_csv()
    print(f"Created sample CSV at: {csv_path}")

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Upload the file using upload_file()
            task = client.upload_file(
                file_path=csv_path,
                check_smtp=True,
                email_column="email",        # Specify the email column name
                preserve_original=True,      # Keep original columns in results
            )

            print(f"\nTask submitted successfully!")
            print(f"Task ID: {task.task_id}")
            print(f"Status: {task.status}")
            print(f"File name: {task.file_name}")
            print(f"Estimated count: {task.estimated_count}")
            print(f"Unique emails: {task.unique_emails}")
            print(f"Status URL: {task.status_url}")

            return task.task_id

        except ValidationError as e:
            print(f"Validation error: {e.message}")
        except Exception as e:
            print(f"Error: {e}")

        finally:
            # Clean up the temporary file
            os.unlink(csv_path)

    return None


def get_task_status_example(task_id: str):
    """Get task status with optional long-polling."""
    print("\n" + "=" * 50)
    print("Getting Task Status")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Get task status without long-polling
            status = client.get_file_task_status(task_id)

            print(f"Task ID: {status.task_id}")
            print(f"Status: {status.status}")
            print(f"Progress: {status.progress}%")
            print(f"Total emails: {status.total_emails}")
            print(f"Processed: {status.processed_emails}")
            print(f"Valid: {status.valid_emails}")
            print(f"Invalid: {status.invalid_emails}")
            print(f"Unknown: {status.unknown_emails}")
            print(f"Credits used: {status.credits_used}")

            # Get task status with long-polling (wait up to 60 seconds for completion)
            print("\nWaiting with long-polling (up to 60 seconds)...")
            status = client.get_file_task_status(
                task_id=task_id,
                timeout=60,  # Long-poll timeout in seconds (0-300)
            )
            print(f"After long-poll - Status: {status.status}")

        except NotFoundError:
            print(f"Task not found: {task_id}")
        except ValidationError as e:
            print(f"Validation error: {e.message}")


def wait_for_completion_example(task_id: str):
    """Wait for task completion using polling."""
    print("\n" + "=" * 50)
    print("Waiting for Task Completion")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Wait for the task to complete
            print("Polling for completion...")
            completed = client.wait_for_file_task(
                task_id=task_id,
                poll_interval=5.0,  # Check every 5 seconds
                max_wait=600.0,     # Maximum wait time of 10 minutes
            )

            print(f"Task completed!")
            print(f"Status: {completed.status}")
            print(f"Total emails: {completed.total_emails}")
            print(f"Valid: {completed.valid_emails}")
            print(f"Invalid: {completed.invalid_emails}")
            print(f"Unknown: {completed.unknown_emails}")
            print(f"Credits used: {completed.credits_used}")

            if completed.completed_at:
                print(f"Completed at: {completed.completed_at}")

            if completed.download_url:
                print(f"Download URL: {completed.download_url}")

            return completed.status == "completed"

        except TimeoutError as e:
            print(f"Timeout waiting for task: {e}")
        except NotFoundError:
            print(f"Task not found: {task_id}")

    return False


def download_results_example(task_id: str):
    """Download task results as CSV with filter options."""
    print("\n" + "=" * 50)
    print("Downloading Task Results")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Download all results
            print("Downloading all results...")
            output = client.download_file_results(
                task_id=task_id,
                output_path="results_all.csv",
            )
            print(f"All results saved to: {output}")

            # Download only valid emails
            print("\nDownloading only valid emails...")
            output = client.download_file_results(
                task_id=task_id,
                output_path="results_valid.csv",
                valid=True,
            )
            print(f"Valid results saved to: {output}")

            # Download only invalid and risky emails
            print("\nDownloading invalid and risky emails...")
            output = client.download_file_results(
                task_id=task_id,
                output_path="results_bad.csv",
                invalid=True,
                risky=True,
            )
            print(f"Invalid/risky results saved to: {output}")

        except NotFoundError:
            print(f"Task not found: {task_id}")
        except ValidationError as e:
            print(f"Validation error: {e.message}")


def full_workflow_example():
    """Run a complete file verification workflow."""
    print("\n" + "=" * 50)
    print("Complete File Verification Workflow")
    print("=" * 50)

    # Create a sample CSV file
    csv_path = create_sample_csv()

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Step 1: Upload the file
            print("\nStep 1: Uploading file...")
            task = client.upload_file(
                file_path=csv_path,
                check_smtp=True,
                email_column="email",
                preserve_original=True,
            )
            print(f"Task created: {task.task_id}")

            # Step 2: Wait for completion
            print("\nStep 2: Waiting for completion...")
            completed = client.wait_for_file_task(
                task_id=task.task_id,
                poll_interval=2.0,
                max_wait=300.0,
            )
            print(f"Task status: {completed.status}")

            if completed.status == "failed":
                print(f"Task failed: {completed.error_message}")
                return

            # Step 3: Download results
            print("\nStep 3: Downloading results...")
            output = client.download_file_results(
                task_id=task.task_id,
                output_path="verification_results.csv",
            )

            # Step 4: Print summary
            print(f"\nSummary:")
            print(f"  Total: {completed.total_emails}")
            print(f"  Valid: {completed.valid_emails}")
            print(f"  Invalid: {completed.invalid_emails}")
            print(f"  Unknown: {completed.unknown_emails}")
            print(f"  Risky: {completed.risky_emails}")
            print(f"  Disposable: {completed.disposable_emails}")
            print(f"  Catchall: {completed.catchall_emails}")
            print(f"  Credits used: {completed.credits_used}")
            print(f"  Results saved to: {output}")

        except TimeoutError as e:
            print(f"Timeout: {e}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Clean up
            os.unlink(csv_path)


if __name__ == "__main__":
    # Run the complete workflow example
    full_workflow_example()

    # Or run individual examples:
    # task_id = upload_file_example()
    # if task_id:
    #     get_task_status_example(task_id)
    #     if wait_for_completion_example(task_id):
    #         download_results_example(task_id)
