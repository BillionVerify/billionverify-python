"""Tests for BillionVerify Python SDK."""

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import httpx
import pytest

from billionverify import (
    AsyncBillionVerify,
    AuthenticationError,
    BillionVerify,
    InsufficientCreditsError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)


# Helper to build a standard API wrapper response
def api_response(data):
    """Build a standard API wrapper response."""
    return {"success": True, "code": "0", "message": "OK", "data": data}


class TestBillionVerifyClient:
    """Tests for BillionVerify client."""

    def test_init_requires_api_key(self):
        """Should raise AuthenticationError when API key is missing."""
        with pytest.raises(AuthenticationError):
            BillionVerify(api_key="")

    def test_init_with_default_options(self):
        """Should create client with default options."""
        client = BillionVerify(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.billionverify.com/v1"
        assert client.timeout == 30.0
        assert client.retries == 3

    def test_init_with_custom_options(self):
        """Should create client with custom options."""
        client = BillionVerify(
            api_key="test-key",
            base_url="https://custom.api.com/v1",
            timeout=60.0,
            retries=5,
        )
        assert client.base_url == "https://custom.api.com/v1"
        assert client.timeout == 60.0
        assert client.retries == 5

    def test_context_manager(self):
        """Should work as context manager."""
        with BillionVerify(api_key="test-key") as client:
            assert client is not None

    @patch.object(httpx.Client, "request")
    def test_verify_success(self, mock_request):
        """Should verify email successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response({
            "email": "test@example.com",
            "status": "valid",
            "score": 0.95,
            "is_deliverable": True,
            "is_disposable": False,
            "is_catchall": False,
            "is_role": False,
            "is_free": False,
            "domain": "example.com",
            "check_smtp": True,
            "reason": "Valid email address",
            "response_time": 150,
            "credits_used": 1,
            "mx_records": ["mx.example.com"],
        })
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.verify("test@example.com")

        assert result.email == "test@example.com"
        assert result.status == "valid"
        assert result.score == 0.95
        assert result.is_deliverable is True
        assert result.is_disposable is False
        assert result.check_smtp is True
        assert result.domain == "example.com"
        assert result.credits_used == 1

    @patch.object(httpx.Client, "request")
    def test_verify_with_domain_suggestion(self, mock_request):
        """Should return domain suggestion when available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response({
            "email": "test@gmial.com",
            "status": "invalid",
            "score": 0.0,
            "is_deliverable": False,
            "is_disposable": False,
            "is_catchall": False,
            "is_role": False,
            "is_free": False,
            "domain": "gmial.com",
            "check_smtp": False,
            "reason": "no_mx_records",
            "domain_suggestion": "gmail.com",
            "response_time": 50,
            "credits_used": 1,
        })
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.verify("test@gmial.com")

        assert result.domain_suggestion == "gmail.com"

    @patch.object(httpx.Client, "request")
    def test_verify_authentication_error(self, mock_request):
        """Should raise AuthenticationError on 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.is_success = False
        mock_response.reason_phrase = "Unauthorized"
        mock_response.json.return_value = {
            "error": {"code": "INVALID_API_KEY", "message": "Invalid API key"}
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            with pytest.raises(AuthenticationError):
                client.verify("test@example.com")

    @patch.object(httpx.Client, "request")
    def test_verify_validation_error(self, mock_request):
        """Should raise ValidationError on 400."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.is_success = False
        mock_response.reason_phrase = "Bad Request"
        mock_response.json.return_value = {
            "error": {"code": "INVALID_EMAIL", "message": "Invalid email format"}
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            with pytest.raises(ValidationError):
                client.verify("invalid")

    @patch.object(httpx.Client, "request")
    def test_verify_insufficient_credits(self, mock_request):
        """Should raise InsufficientCreditsError on 402."""
        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.is_success = False
        mock_response.reason_phrase = "Payment Required"
        mock_response.json.return_value = {
            "error": {"code": "INSUFFICIENT_CREDITS", "message": "Not enough credits"}
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            with pytest.raises(InsufficientCreditsError):
                client.verify("test@example.com")

    @patch.object(httpx.Client, "request")
    def test_verify_not_found(self, mock_request):
        """Should raise NotFoundError on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.is_success = False
        mock_response.reason_phrase = "Not Found"
        mock_response.json.return_value = {
            "error": {"code": "NOT_FOUND", "message": "Resource not found"}
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            with pytest.raises(NotFoundError):
                client.verify("test@example.com")

    @patch.object(httpx.Client, "request")
    def test_verify_bulk_success(self, mock_request):
        """Should verify bulk emails successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response({
            "results": [
                {
                    "email": "user1@example.com",
                    "status": "valid",
                    "score": 0.95,
                    "is_deliverable": True,
                    "is_disposable": False,
                    "is_catchall": False,
                    "is_role": False,
                    "is_free": False,
                    "domain": "example.com",
                    "reason": "Valid email address",
                },
                {
                    "email": "bad@invalid.com",
                    "status": "invalid",
                    "score": 0.0,
                    "is_deliverable": False,
                    "is_disposable": False,
                    "is_catchall": False,
                    "is_role": False,
                    "is_free": False,
                    "domain": "invalid.com",
                    "reason": "no_mx_records",
                },
            ],
            "total_emails": 2,
            "valid_emails": 1,
            "invalid_emails": 1,
            "credits_used": 2,
            "process_time": 500,
        })
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.verify_bulk(["user1@example.com", "bad@invalid.com"])

        assert result.total_emails == 2
        assert result.valid_emails == 1
        assert result.invalid_emails == 1
        assert len(result.results) == 2
        assert result.results[0].email == "user1@example.com"
        assert result.results[0].status == "valid"

    def test_verify_bulk_too_many_emails(self):
        """Should raise ValidationError when emails exceed 50."""
        emails = ["test@example.com"] * 51

        with BillionVerify(api_key="test-key") as client:
            with pytest.raises(ValidationError):
                client.verify_bulk(emails)

    @patch.object(httpx.Client, "request")
    def test_get_credits(self, mock_request):
        """Should get credits successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response({
            "account_id": "acc_123",
            "api_key_id": "key_123",
            "api_key_name": "Test Key",
            "credits_balance": 9500,
            "credits_consumed": 500,
            "credits_added": 10000,
            "last_updated": "2025-01-15T10:30:00Z",
        })
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.get_credits()

        assert result.credits_balance == 9500
        assert result.credits_consumed == 500
        assert result.api_key_name == "Test Key"

    @patch.object(httpx.Client, "request")
    def test_get_file_task_status(self, mock_request):
        """Should get file task status successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response({
            "task_id": "task_123",
            "status": "processing",
            "progress": 50,
            "total_emails": 100,
            "processed_emails": 50,
            "valid_emails": 40,
            "invalid_emails": 5,
            "unknown_emails": 5,
            "credits_used": 50,
        })
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.get_file_task_status("task_123")

        assert result.task_id == "task_123"
        assert result.status == "processing"
        assert result.progress == 50
        assert result.total_emails == 100
        assert result.processed_emails == 50

    @patch.object(httpx.Client, "request")
    def test_create_webhook(self, mock_request):
        """Should create webhook successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response({
            "id": "webhook_123",
            "url": "https://example.com/webhook",
            "events": ["file.completed", "file.failed"],
            "secret": "whsec_test123",
            "is_active": True,
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T10:30:00Z",
        })
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.create_webhook(
                url="https://example.com/webhook",
                events=["file.completed", "file.failed"],
            )

        assert result.id == "webhook_123"
        assert result.url == "https://example.com/webhook"
        assert result.secret == "whsec_test123"
        assert result.is_active is True

    @patch.object(httpx.Client, "request")
    def test_list_webhooks(self, mock_request):
        """Should list webhooks successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response([
            {
                "id": "webhook_123",
                "url": "https://example.com/webhook",
                "events": ["file.completed"],
                "secret": None,
                "is_active": True,
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:00Z",
            }
        ])
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.list_webhooks()

        assert len(result) == 1
        assert result[0].id == "webhook_123"

    @patch.object(httpx.Client, "request")
    def test_delete_webhook(self, mock_request):
        """Should delete webhook successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.is_success = True
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            client.delete_webhook("webhook_123")

        mock_request.assert_called_once()

    def test_verify_webhook_signature_valid(self):
        """Should verify valid webhook signature."""
        payload = '{"event":"test"}'
        secret = "test-secret"
        expected_sig = "sha256=" + hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        result = BillionVerify.verify_webhook_signature(payload, expected_sig, secret)

        assert result is True

    def test_verify_webhook_signature_invalid(self):
        """Should reject invalid webhook signature."""
        payload = '{"event":"test"}'
        secret = "test-secret"
        invalid_sig = "sha256=invalid"

        result = BillionVerify.verify_webhook_signature(payload, invalid_sig, secret)

        assert result is False


class TestExceptions:
    """Tests for exception classes."""

    def test_authentication_error(self):
        """Should create AuthenticationError correctly."""
        error = AuthenticationError()
        assert error.code == "INVALID_API_KEY"
        assert error.status_code == 401

    def test_rate_limit_error(self):
        """Should create RateLimitError with retry_after."""
        error = RateLimitError("Rate limited", retry_after=60)
        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert error.retry_after == 60

    def test_validation_error(self):
        """Should create ValidationError with details."""
        error = ValidationError("Invalid input", details="Email format is wrong")
        assert error.code == "INVALID_REQUEST"
        assert error.details == "Email format is wrong"

    def test_insufficient_credits_error(self):
        """Should create InsufficientCreditsError correctly."""
        error = InsufficientCreditsError()
        assert error.code == "INSUFFICIENT_CREDITS"
        assert error.status_code == 402

    def test_not_found_error(self):
        """Should create NotFoundError correctly."""
        error = NotFoundError()
        assert error.code == "NOT_FOUND"
        assert error.status_code == 404

    def test_timeout_error(self):
        """Should create TimeoutError correctly."""
        error = TimeoutError("Request timed out after 30s")
        assert error.code == "TIMEOUT"
        assert error.message == "Request timed out after 30s"


@pytest.mark.asyncio
class TestAsyncBillionVerifyClient:
    """Tests for async BillionVerify client."""

    async def test_init_requires_api_key(self):
        """Should raise AuthenticationError when API key is missing."""
        with pytest.raises(AuthenticationError):
            AsyncBillionVerify(api_key="")

    @patch.object(httpx.AsyncClient, "request")
    async def test_verify_success(self, mock_request):
        """Should verify email successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = api_response({
            "email": "test@example.com",
            "status": "valid",
            "score": 0.95,
            "is_deliverable": True,
            "is_disposable": False,
            "is_catchall": False,
            "is_role": False,
            "is_free": False,
            "domain": "example.com",
            "check_smtp": True,
            "reason": "Valid email address",
            "response_time": 150,
            "credits_used": 1,
        })
        mock_request.return_value = mock_response

        async with AsyncBillionVerify(api_key="test-key") as client:
            result = await client.verify("test@example.com")

        assert result.email == "test@example.com"
        assert result.status == "valid"
        assert result.check_smtp is True
