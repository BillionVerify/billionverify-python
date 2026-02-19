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
        mock_response.json.return_value = {
            "email": "test@example.com",
            "status": "valid",
            "result": {
                "deliverable": True,
                "valid_format": True,
                "valid_domain": True,
                "valid_mx": True,
                "disposable": False,
                "role": False,
                "catchall": False,
                "free": False,
                "smtp_valid": True,
            },
            "score": 0.95,
            "reason": None,
            "credits_used": 1,
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.verify("test@example.com")

        assert result.email == "test@example.com"
        assert result.status == "valid"
        assert result.score == 0.95
        assert result.result.deliverable is True
        assert result.result.disposable is False

    @patch.object(httpx.Client, "request")
    def test_verify_with_options(self, mock_request):
        """Should verify email with custom options."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "email": "test@example.com",
            "status": "valid",
            "result": {
                "deliverable": True,
                "valid_format": True,
                "valid_domain": True,
                "valid_mx": True,
                "disposable": False,
                "role": False,
                "catchall": False,
                "free": False,
                "smtp_valid": True,
            },
            "score": 0.95,
            "reason": None,
            "credits_used": 1,
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.verify("test@example.com", smtp_check=False, timeout=5000)

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"]["smtp_check"] is False
        assert call_kwargs["json"]["timeout"] == 5000

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
        """Should raise InsufficientCreditsError on 403."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.is_success = False
        mock_response.reason_phrase = "Forbidden"
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
        """Should submit bulk verification job successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "job_id": "job_123",
            "status": "processing",
            "total": 3,
            "processed": 0,
            "valid": 0,
            "invalid": 0,
            "unknown": 0,
            "credits_used": 3,
            "created_at": "2025-01-15T10:30:00Z",
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.verify_bulk(
                ["user1@example.com", "user2@example.com", "user3@example.com"]
            )

        assert result.job_id == "job_123"
        assert result.status == "processing"
        assert result.total == 3

    def test_verify_bulk_too_many_emails(self):
        """Should raise ValidationError when emails exceed 10000."""
        emails = ["test@example.com"] * 10001

        with BillionVerify(api_key="test-key") as client:
            with pytest.raises(ValidationError):
                client.verify_bulk(emails)

    @patch.object(httpx.Client, "request")
    def test_get_bulk_job_status(self, mock_request):
        """Should get bulk job status successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "job_id": "job_123",
            "status": "processing",
            "total": 100,
            "processed": 50,
            "valid": 40,
            "invalid": 5,
            "unknown": 5,
            "credits_used": 100,
            "created_at": "2025-01-15T10:30:00Z",
            "progress_percent": 50,
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.get_bulk_job_status("job_123")

        assert result.job_id == "job_123"
        assert result.progress_percent == 50

    @patch.object(httpx.Client, "request")
    def test_get_bulk_job_results(self, mock_request):
        """Should get bulk job results successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "job_id": "job_123",
            "total": 100,
            "limit": 50,
            "offset": 0,
            "results": [
                {
                    "email": "test@example.com",
                    "status": "valid",
                    "result": {"deliverable": True},
                    "score": 0.95,
                }
            ],
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.get_bulk_job_results("job_123", limit=50, offset=0)

        assert result.job_id == "job_123"
        assert len(result.results) == 1
        assert result.results[0].email == "test@example.com"

    @patch.object(httpx.Client, "request")
    def test_get_credits(self, mock_request):
        """Should get credits successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "available": 9500,
            "used": 500,
            "total": 10000,
            "plan": "Professional",
            "resets_at": "2025-02-01T00:00:00Z",
            "rate_limit": {"requests_per_hour": 10000, "remaining": 9850},
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.get_credits()

        assert result.available == 9500
        assert result.plan == "Professional"
        assert result.rate_limit.remaining == 9850

    @patch.object(httpx.Client, "request")
    def test_create_webhook(self, mock_request):
        """Should create webhook successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "id": "webhook_123",
            "url": "https://example.com/webhook",
            "events": ["verification.completed"],
            "created_at": "2025-01-15T10:30:00Z",
        }
        mock_request.return_value = mock_response

        with BillionVerify(api_key="test-key") as client:
            result = client.create_webhook(
                url="https://example.com/webhook",
                events=["verification.completed"],
            )

        assert result.id == "webhook_123"
        assert result.url == "https://example.com/webhook"

    @patch.object(httpx.Client, "request")
    def test_list_webhooks(self, mock_request):
        """Should list webhooks successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = [
            {
                "id": "webhook_123",
                "url": "https://example.com/webhook",
                "events": ["verification.completed"],
                "created_at": "2025-01-15T10:30:00Z",
            }
        ]
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
        assert error.status_code == 403

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
        mock_response.json.return_value = {
            "email": "test@example.com",
            "status": "valid",
            "result": {
                "deliverable": True,
                "valid_format": True,
                "valid_domain": True,
                "valid_mx": True,
                "disposable": False,
                "role": False,
                "catchall": False,
                "free": False,
                "smtp_valid": True,
            },
            "score": 0.95,
            "reason": None,
            "credits_used": 1,
        }
        mock_request.return_value = mock_response

        async with AsyncBillionVerify(api_key="test-key") as client:
            result = await client.verify("test@example.com")

        assert result.email == "test@example.com"
        assert result.status == "valid"
