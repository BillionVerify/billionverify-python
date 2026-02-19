"""BillionVerify SDK Exceptions."""

from typing import Optional


class BillionVerifyError(Exception):
    """Base exception for BillionVerify SDK."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int = 0,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class AuthenticationError(BillionVerifyError):
    """Raised when API key is invalid or missing."""

    def __init__(self, message: str = "Invalid or missing API key") -> None:
        super().__init__(message, "INVALID_API_KEY", 401)


class RateLimitError(BillionVerifyError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: int = 0
    ) -> None:
        super().__init__(message, "RATE_LIMIT_EXCEEDED", 429)
        self.retry_after = retry_after


class ValidationError(BillionVerifyError):
    """Raised when request validation fails."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message, "INVALID_REQUEST", 400, details)


class InsufficientCreditsError(BillionVerifyError):
    """Raised when there are not enough credits."""

    def __init__(self, message: str = "Insufficient credits") -> None:
        super().__init__(message, "INSUFFICIENT_CREDITS", 402)


class NotFoundError(BillionVerifyError):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, "NOT_FOUND", 404)


class TimeoutError(BillionVerifyError):
    """Raised when a request times out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message, "TIMEOUT", 504)
