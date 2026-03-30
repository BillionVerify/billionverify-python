"""BillionVerify SDK Types."""

from dataclasses import dataclass
from typing import List, Literal, Optional


VerificationStatus = Literal["valid", "invalid", "unknown", "risky", "disposable", "catchall", "role"]
JobStatus = Literal["pending", "processing", "completed", "failed"]
WebhookEvent = Literal["file.completed", "file.failed"]


@dataclass
class DomainReputation:
    """Domain reputation details."""

    mx_ip: str
    is_listed: bool
    blacklists: List[str]
    checked: bool


@dataclass
class VerificationResult:
    """Detailed verification result."""

    email: str
    status: VerificationStatus
    score: float
    is_deliverable: bool
    is_disposable: bool
    is_catchall: bool
    is_role: bool
    is_free: bool
    domain: str
    domain_age: Optional[int]
    mx_records: List[str]
    domain_reputation: Optional[DomainReputation]
    smtp_check: bool
    reason: str
    suggestion: Optional[str]
    response_time: int
    credits_used: int


@dataclass
class BulkVerificationResult:
    """Result from synchronous bulk verification."""

    email: str
    status: VerificationStatus
    score: float
    is_deliverable: bool
    is_disposable: bool
    is_catchall: bool
    is_role: bool
    is_free: bool
    domain: str
    reason: str


@dataclass
class BulkVerifyResponse:
    """Response from synchronous bulk verification."""

    results: List[BulkVerificationResult]
    total_emails: int
    valid_emails: int
    invalid_emails: int
    credits_used: int
    process_time: int


@dataclass
class FileJobResponse:
    """Response from file verification job."""

    job_id: str
    status: JobStatus
    total: int
    processed: int
    valid: int
    invalid: int
    unknown: int
    credits_used: int
    created_at: str
    completed_at: Optional[str] = None
    progress_percent: Optional[int] = None
    filename: Optional[str] = None


@dataclass
class FileResultItem:
    """Single result item from file verification."""

    email: str
    status: VerificationStatus
    score: float
    is_deliverable: bool
    is_disposable: bool
    is_catchall: bool
    is_role: bool
    is_free: bool
    domain: str
    reason: str
    original_row: Optional[dict] = None


@dataclass
class FileResultsResponse:
    """Response from file job results."""

    job_id: str
    total: int
    limit: int
    offset: int
    results: List[FileResultItem]


@dataclass
class CreditsResponse:
    """Response from credits endpoint."""

    account_id: str
    api_key_id: str
    api_key_name: str
    credits_balance: int
    credits_consumed: int
    credits_added: int
    last_updated: str


@dataclass
class Webhook:
    """Webhook configuration."""

    id: str
    url: str
    events: List[WebhookEvent]
    secret: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


@dataclass
class HealthCheckResponse:
    """Response from health check endpoint."""

    status: str
    version: Optional[str] = None
