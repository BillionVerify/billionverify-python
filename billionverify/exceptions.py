"""BillionVerify Python SDK Exceptions."""

from typing import Any, Optional


class BillionVerifyError(Exception):
    """Base exception for BillionVerify SDK."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int = 0,
        details: Optional[str] = None,
        response_metadata: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        self.response_metadata = response_metadata

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class AuthenticationError(BillionVerifyError):
    """Raised when API key is invalid or missing."""

    def __init__(self, message: str = "Invalid or missing API key", response_metadata: Optional[Any] = None) -> None:
        super().__init__(message, "INVALID_API_KEY", 401, response_metadata=response_metadata)


class RateLimitError(BillionVerifyError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 0,
        response_metadata: Optional[Any] = None,
    ) -> None:
        super().__init__(message, "RATE_LIMIT_EXCEEDED", 429, response_metadata=response_metadata)
        self.retry_after = retry_after


class ValidationError(BillionVerifyError):
    """Raised when request validation fails."""

    def __init__(self, message: str, details: Optional[str] = None, response_metadata: Optional[Any] = None) -> None:
        super().__init__(message, "INVALID_REQUEST", 400, details, response_metadata=response_metadata)


class InsufficientCreditsError(BillionVerifyError):
    """Raised when there are not enough credits."""

    def __init__(self, message: str = "Insufficient credits", response_metadata: Optional[Any] = None) -> None:
        super().__init__(message, "INSUFFICIENT_CREDITS", 402, response_metadata=response_metadata)


class NotFoundError(BillionVerifyError):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found", response_metadata: Optional[Any] = None) -> None:
        super().__init__(message, "NOT_FOUND", 404, response_metadata=response_metadata)


class TimeoutError(BillionVerifyError):
    """Raised when a request times out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message, "TIMEOUT", 504)
