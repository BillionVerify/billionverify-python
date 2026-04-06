"""BillionVerify Python SDK for email verification."""

from .client import AsyncBillionVerify, BillionVerify
from .exceptions import (
    AuthenticationError,
    BillionVerifyError,
    InsufficientCreditsError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)
from .types import (
    BulkVerificationResult,
    BulkVerifyResponse,
    CreditsResponse,
    DomainReputation,
    FileTaskStatus,
    FileUploadResponse,
    HealthCheckResponse,
    JobStatus,
    VerificationResult,
    VerificationStatus,
    Webhook,
    WebhookEvent,
)

__version__ = "1.1.0"

__all__ = [
    # Clients
    "BillionVerify",
    "AsyncBillionVerify",
    # Types
    "VerificationResult",
    "VerificationStatus",
    "BulkVerificationResult",
    "BulkVerifyResponse",
    "FileUploadResponse",
    "FileTaskStatus",
    "CreditsResponse",
    "HealthCheckResponse",
    "DomainReputation",
    "JobStatus",
    "Webhook",
    "WebhookEvent",
    # Exceptions
    "BillionVerifyError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "InsufficientCreditsError",
    "NotFoundError",
    "TimeoutError",
]
