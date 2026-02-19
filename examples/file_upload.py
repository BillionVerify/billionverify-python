"""File upload example for BillionVerify SDK.

This example demonstrates:
- File upload using upload_file() for async verification
- Getting job status with get_file_job_status() (with timeout for long-polling)
- Downloading results with get_file_job_results() with filter options
- Waiting for job completion using wait_for_file_job()
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
            job = client.upload_file(
                file_path=csv_path,
                check_smtp=True,
                email_column="email",        # Specify the email column name
                preserve_original=True,      # Keep original columns in results
            )

            print(f"\nJob submitted successfully!")
            print(f"Job ID: {job.job_id}")
            print(f"Status: {job.status}")
            print(f"Total emails: {job.total}")
            print(f"Filename: {job.filename}")
            print(f"Created at: {job.created_at}")

            return job.job_id

        except ValidationError as e:
            print(f"Validation error: {e.message}")
        except Exception as e:
            print(f"Error: {e}")

        finally:
            # Clean up the temporary file
            os.unlink(csv_path)

    return None


def get_job_status_example(job_id: str):
    """Get job status with optional long-polling."""
    print("\n" + "=" * 50)
    print("Getting Job Status")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Get job status without long-polling
            status = client.get_file_job_status(job_id)

            print(f"Job ID: {status.job_id}")
            print(f"Status: {status.status}")
            print(f"Progress: {status.progress_percent}%")
            print(f"Total: {status.total}")
            print(f"Processed: {status.processed}")
            print(f"Valid: {status.valid}")
            print(f"Invalid: {status.invalid}")
            print(f"Unknown: {status.unknown}")
            print(f"Credits used: {status.credits_used}")

            # Get job status with long-polling (wait up to 60 seconds for completion)
            print("\nWaiting with long-polling (up to 60 seconds)...")
            status = client.get_file_job_status(
                job_id=job_id,
                timeout=60,  # Long-poll timeout in seconds (0-300)
            )
            print(f"After long-poll - Status: {status.status}")

        except NotFoundError:
            print(f"Job not found: {job_id}")
        except ValidationError as e:
            print(f"Validation error: {e.message}")


def wait_for_completion_example(job_id: str):
    """Wait for job completion using polling."""
    print("\n" + "=" * 50)
    print("Waiting for Job Completion")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Wait for the job to complete
            print("Polling for completion...")
            completed = client.wait_for_file_job(
                job_id=job_id,
                poll_interval=5.0,  # Check every 5 seconds
                max_wait=600.0,     # Maximum wait time of 10 minutes
            )

            print(f"Job completed!")
            print(f"Status: {completed.status}")
            print(f"Total: {completed.total}")
            print(f"Valid: {completed.valid}")
            print(f"Invalid: {completed.invalid}")
            print(f"Unknown: {completed.unknown}")
            print(f"Credits used: {completed.credits_used}")

            if completed.completed_at:
                print(f"Completed at: {completed.completed_at}")

            return completed.status == "completed"

        except TimeoutError as e:
            print(f"Timeout waiting for job: {e}")
        except NotFoundError:
            print(f"Job not found: {job_id}")

    return False


def get_results_example(job_id: str):
    """Get job results with filter options."""
    print("\n" + "=" * 50)
    print("Getting Job Results")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Get all results
            print("Fetching all results...")
            results = client.get_file_job_results(
                job_id=job_id,
                limit=100,
                offset=0,
            )

            print(f"Job ID: {results.job_id}")
            print(f"Total: {results.total}")
            print(f"Returned: {len(results.results)} (limit: {results.limit}, offset: {results.offset})")

            print("\nAll Results:")
            for item in results.results:
                print(f"\n  {item.email}:")
                print(f"    Status: {item.status}")
                print(f"    Score: {item.score}")
                print(f"    Deliverable: {item.is_deliverable}")
                print(f"    Disposable: {item.is_disposable}")
                print(f"    Catchall: {item.is_catchall}")
                print(f"    Role: {item.is_role}")
                print(f"    Domain: {item.domain}")
                print(f"    Reason: {item.reason}")
                if item.original_row:
                    print(f"    Original data: {item.original_row}")

            # Get only valid emails
            print("\n" + "-" * 30)
            print("Fetching only valid emails...")
            valid_results = client.get_file_job_results(
                job_id=job_id,
                valid=True,
                invalid=False,
                unknown=False,
                disposable=False,
                catchall=False,
                role=False,
                risky=False,
            )
            print(f"Valid emails: {len(valid_results.results)}")

            # Get only invalid and risky emails
            print("\n" + "-" * 30)
            print("Fetching invalid and risky emails...")
            bad_results = client.get_file_job_results(
                job_id=job_id,
                valid=False,
                invalid=True,
                risky=True,
            )
            print(f"Invalid/risky emails: {len(bad_results.results)}")

            # Pagination example
            print("\n" + "-" * 30)
            print("Pagination example...")
            page_size = 2
            offset = 0
            all_emails = []

            while True:
                page = client.get_file_job_results(
                    job_id=job_id,
                    limit=page_size,
                    offset=offset,
                )
                all_emails.extend(page.results)
                print(f"  Fetched {len(page.results)} results (offset: {offset})")

                if len(page.results) < page_size:
                    break
                offset += page_size

            print(f"Total fetched via pagination: {len(all_emails)}")

        except NotFoundError:
            print(f"Job not found: {job_id}")
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
            job = client.upload_file(
                file_path=csv_path,
                check_smtp=True,
                email_column="email",
                preserve_original=True,
            )
            print(f"Job created: {job.job_id}")

            # Step 2: Wait for completion
            print("\nStep 2: Waiting for completion...")
            completed = client.wait_for_file_job(
                job_id=job.job_id,
                poll_interval=2.0,
                max_wait=300.0,
            )
            print(f"Job status: {completed.status}")

            if completed.status == "failed":
                print("Job failed!")
                return

            # Step 3: Get results
            print("\nStep 3: Fetching results...")
            results = client.get_file_job_results(job.job_id)

            # Step 4: Process results
            print("\nStep 4: Processing results...")
            valid_count = sum(1 for r in results.results if r.status == "valid")
            invalid_count = sum(1 for r in results.results if r.status == "invalid")
            disposable_count = sum(1 for r in results.results if r.is_disposable)
            catchall_count = sum(1 for r in results.results if r.is_catchall)

            print(f"\nSummary:")
            print(f"  Total: {results.total}")
            print(f"  Valid: {valid_count}")
            print(f"  Invalid: {invalid_count}")
            print(f"  Disposable: {disposable_count}")
            print(f"  Catch-all: {catchall_count}")
            print(f"  Credits used: {completed.credits_used}")

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
    # job_id = upload_file_example()
    # if job_id:
    #     get_job_status_example(job_id)
    #     if wait_for_completion_example(job_id):
    #         get_results_example(job_id)
