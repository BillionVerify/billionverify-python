"""BillionVerify Python SDK Types."""

from dataclasses import dataclass, field
from typing import List, Literal, Optional


VerificationStatus = Literal["valid", "invalid", "unknown", "risky", "disposable", "catchall", "role"]
JobStatus = Literal["pending", "parsing", "processing", "completed", "failed"]
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
    check_smtp: bool
    reason: str
    response_time: int
    credits_used: int
    domain_age: Optional[int] = None
    mx_records: List[str] = field(default_factory=list)
    domain_reputation: Optional[DomainReputation] = None
    domain_suggestion: Optional[str] = None
    has_gravatar: bool = False
    gravatar_url: Optional[str] = None
    smtp_response: Optional[str] = None
    error_message: Optional[str] = None


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
class FileUploadResponse:
    """Response from file upload endpoint."""

    task_id: str
    file_name: str
    file_size: int
    status: str
    message: str
    status_url: str
    created_at: str
    estimated_count: int
    unique_emails: Optional[int] = None
    total_rows: Optional[int] = None
    email_column: Optional[str] = None


@dataclass
class FileTaskStatus:
    """Response from file task status endpoint."""

    task_id: str
    status: JobStatus
    progress: int
    total_emails: int
    processed_emails: int
    valid_emails: int
    invalid_emails: int
    unknown_emails: int
    credits_used: int
    risky_emails: int = 0
    disposable_emails: int = 0
    role_emails: int = 0
    catchall_emails: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    download_url: Optional[str] = None
    direct_download_url: Optional[str] = None
    direct_download_expires_at: Optional[str] = None
    can_pause: bool = False
    can_resume: bool = False
    can_restart: bool = False
    total_chunks: Optional[int] = None
    completed_chunks: Optional[int] = None
    failed_chunks: Optional[int] = None
    unique_emails: Optional[int] = None
    total_rows: Optional[int] = None


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
