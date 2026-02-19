"""Webhooks example for BillionVerify SDK.

This example demonstrates:
- Creating webhooks (events: file.completed, file.failed)
- Listing webhooks
- Deleting webhooks
- Verifying webhook signatures
"""

import hashlib
import hmac
import json
import os

from billionverify import BillionVerify, NotFoundError, ValidationError

# Get API key from environment variable
API_KEY = os.getenv("BILLIONVERIFY_API_KEY", "your-api-key")


def create_webhook_example():
    """Create a new webhook."""
    print("=" * 50)
    print("Creating Webhook")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            # Create a webhook for file verification events
            # Available events: file.completed, file.failed
            webhook = client.create_webhook(
                url="https://your-app.com/webhooks/billionverify",
                events=["file.completed", "file.failed"],
            )

            print(f"Webhook created successfully!")
            print(f"ID: {webhook.id}")
            print(f"URL: {webhook.url}")
            print(f"Events: {webhook.events}")
            print(f"Active: {webhook.is_active}")
            print(f"Created at: {webhook.created_at}")

            # IMPORTANT: Save the secret! It's only returned on creation
            if webhook.secret:
                print(f"\nSecret (save this!): {webhook.secret}")
                print("Use this secret to verify webhook signatures.")

            return webhook

        except ValidationError as e:
            print(f"Validation error: {e.message}")
        except Exception as e:
            print(f"Error: {e}")

    return None


def list_webhooks_example():
    """List all webhooks."""
    print("\n" + "=" * 50)
    print("Listing Webhooks")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            webhooks = client.list_webhooks()

            if not webhooks:
                print("No webhooks configured.")
                return []

            print(f"Found {len(webhooks)} webhook(s):\n")

            for wh in webhooks:
                print(f"Webhook: {wh.id}")
                print(f"  URL: {wh.url}")
                print(f"  Events: {', '.join(wh.events)}")
                print(f"  Active: {wh.is_active}")
                print(f"  Created: {wh.created_at}")
                print(f"  Updated: {wh.updated_at}")
                print()

            return webhooks

        except Exception as e:
            print(f"Error: {e}")

    return []


def delete_webhook_example(webhook_id: str):
    """Delete a webhook."""
    print("\n" + "=" * 50)
    print("Deleting Webhook")
    print("=" * 50)

    with BillionVerify(api_key=API_KEY) as client:
        try:
            client.delete_webhook(webhook_id)
            print(f"Webhook {webhook_id} deleted successfully!")
            return True

        except NotFoundError:
            print(f"Webhook not found: {webhook_id}")
        except Exception as e:
            print(f"Error: {e}")

    return False


def verify_webhook_signature_example():
    """Verify a webhook signature."""
    print("\n" + "=" * 50)
    print("Verifying Webhook Signature")
    print("=" * 50)

    # Example webhook payload (as would be received from BillionVerify)
    webhook_payload = {
        "event": "file.completed",
        "data": {
            "job_id": "job_abc123xyz",
            "status": "completed",
            "total": 100,
            "valid": 85,
            "invalid": 10,
            "unknown": 5,
        },
        "timestamp": "2024-01-15T10:30:00Z",
    }

    # The raw body as received (JSON string)
    raw_body = json.dumps(webhook_payload, separators=(",", ":"))

    # Your webhook secret (from when you created the webhook)
    webhook_secret = "your-webhook-secret"

    # Calculate what the signature should be
    expected_signature = f"sha256={hmac.new(webhook_secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()}"

    print(f"Raw body: {raw_body}")
    print(f"Webhook secret: {webhook_secret}")
    print(f"Expected signature: {expected_signature}")

    # Verify using the SDK's static method
    is_valid = BillionVerify.verify_webhook_signature(
        payload=raw_body,
        signature=expected_signature,
        secret=webhook_secret,
    )

    print(f"\nSignature valid: {is_valid}")

    # Test with an invalid signature
    print("\nTesting with invalid signature...")
    is_invalid = BillionVerify.verify_webhook_signature(
        payload=raw_body,
        signature="sha256=invalid_signature",
        secret=webhook_secret,
    )
    print(f"Invalid signature test: {not is_invalid} (should be True)")


def flask_webhook_handler_example():
    """Example Flask webhook handler (for reference, not runnable)."""
    example_code = '''
# Example Flask webhook handler
from flask import Flask, request, jsonify
from billionverify import BillionVerify

app = Flask(__name__)

WEBHOOK_SECRET = "your-webhook-secret"

@app.route("/webhooks/billionverify", methods=["POST"])
def handle_webhook():
    # Get the signature from the header
    signature = request.headers.get("X-EV-Signature")
    if not signature:
        return jsonify({"error": "Missing signature"}), 401

    # Get the raw body
    raw_body = request.get_data(as_text=True)

    # Verify the signature
    if not BillionVerify.verify_webhook_signature(
        payload=raw_body,
        signature=signature,
        secret=WEBHOOK_SECRET,
    ):
        return jsonify({"error": "Invalid signature"}), 401

    # Parse the payload
    data = request.get_json()
    event = data.get("event")

    if event == "file.completed":
        job_data = data.get("data", {})
        print(f"File job completed: {job_data.get('job_id')}")
        print(f"  Valid: {job_data.get('valid')}")
        print(f"  Invalid: {job_data.get('invalid')}")
        # Process the completed job...

    elif event == "file.failed":
        job_data = data.get("data", {})
        print(f"File job failed: {job_data.get('job_id')}")
        print(f"  Error: {job_data.get('error')}")
        # Handle the failure...

    return jsonify({"status": "ok"}), 200
'''
    print("\n" + "=" * 50)
    print("Example Flask Webhook Handler")
    print("=" * 50)
    print(example_code)


def fastapi_webhook_handler_example():
    """Example FastAPI webhook handler (for reference, not runnable)."""
    example_code = '''
# Example FastAPI webhook handler
from fastapi import FastAPI, Request, HTTPException
from billionverify import BillionVerify

app = FastAPI()

WEBHOOK_SECRET = "your-webhook-secret"

@app.post("/webhooks/billionverify")
async def handle_webhook(request: Request):
    # Get the signature from the header
    signature = request.headers.get("X-EV-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    # Get the raw body
    raw_body = await request.body()

    # Verify the signature
    if not BillionVerify.verify_webhook_signature(
        payload=raw_body.decode("utf-8"),
        signature=signature,
        secret=WEBHOOK_SECRET,
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse the payload
    data = await request.json()
    event = data.get("event")

    if event == "file.completed":
        job_data = data.get("data", {})
        print(f"File job completed: {job_data.get('job_id')}")
        # Process the completed job...

    elif event == "file.failed":
        job_data = data.get("data", {})
        print(f"File job failed: {job_data.get('job_id')}")
        # Handle the failure...

    return {"status": "ok"}
'''
    print("\n" + "=" * 50)
    print("Example FastAPI Webhook Handler")
    print("=" * 50)
    print(example_code)


def webhook_payload_examples():
    """Show example webhook payloads."""
    print("\n" + "=" * 50)
    print("Webhook Payload Examples")
    print("=" * 50)

    file_completed_payload = {
        "event": "file.completed",
        "data": {
            "job_id": "job_abc123xyz",
            "status": "completed",
            "total": 1000,
            "processed": 1000,
            "valid": 850,
            "invalid": 100,
            "unknown": 30,
            "risky": 15,
            "disposable": 3,
            "catchall": 2,
            "credits_used": 1000,
            "filename": "contacts.csv",
            "created_at": "2024-01-15T10:00:00Z",
            "completed_at": "2024-01-15T10:05:30Z",
        },
        "timestamp": "2024-01-15T10:05:30Z",
    }

    file_failed_payload = {
        "event": "file.failed",
        "data": {
            "job_id": "job_def456uvw",
            "status": "failed",
            "error": "Invalid file format",
            "filename": "invalid.txt",
            "created_at": "2024-01-15T11:00:00Z",
        },
        "timestamp": "2024-01-15T11:00:05Z",
    }

    print("\nfile.completed event:")
    print(json.dumps(file_completed_payload, indent=2))

    print("\nfile.failed event:")
    print(json.dumps(file_failed_payload, indent=2))


if __name__ == "__main__":
    # Verify webhook signature (no API calls needed)
    verify_webhook_signature_example()

    # Show example payloads
    webhook_payload_examples()

    # Show example handlers
    flask_webhook_handler_example()
    fastapi_webhook_handler_example()

    # Uncomment to run API examples (requires valid API key)
    # webhook = create_webhook_example()
    # list_webhooks_example()
    # if webhook:
    #     delete_webhook_example(webhook.id)
