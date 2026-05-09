"""BillionVerify Python SDK Client."""

import hashlib
import hmac
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

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
    ResponseMetadata,
    VerificationResult,
    Webhook,
    WebhookEvent,
)

DEFAULT_BASE_URL = "https://api.billionverify.com/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3
SDK_VERSION = "1.1.0"


def _parse_str_header(value: Any) -> Optional[str]:
    if isinstance(value, str) and value:
        return value
    return None


def _parse_int_header(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if not isinstance(value, (str, int)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _response_metadata(response: httpx.Response) -> ResponseMetadata:
    return ResponseMetadata(
        status_code=response.status_code,
        request_id=_parse_str_header(response.headers.get("X-Request-ID")),
        rate_limit_limit=_parse_int_header(response.headers.get("X-RateLimit-Limit")),
        rate_limit_remaining=_parse_int_header(response.headers.get("X-RateLimit-Remaining")),
        rate_limit_reset=_parse_int_header(response.headers.get("X-RateLimit-Reset")),
        retry_after=_parse_int_header(response.headers.get("Retry-After")),
    )


class BillionVerify:
    """BillionVerify API Client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        """Initialize the BillionVerify client.

        Args:
            api_key: Your BillionVerify API key.
            base_url: API base URL (default: https://api.billionverify.com/v1).
            timeout: Request timeout in seconds (default: 30).
            retries: Number of retries for failed requests (default: 3).
        """
        if not api_key:
            raise AuthenticationError("API key is required")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "BV-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": f"billionverify-python/{SDK_VERSION}",
            },
        )

    def __enter__(self) -> "BillionVerify":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        attempt: int = 1,
        files: Optional[Dict[str, Any]] = None,
        custom_timeout: Optional[float] = None,
        skip_auth: bool = False,
        return_metadata: bool = False,
    ) -> Any:
        """Make an HTTP request to the API."""
        try:
            headers = {}
            if skip_auth:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": f"billionverify-python/{SDK_VERSION}",
                }

            request_timeout = custom_timeout if custom_timeout else self.timeout

            if files:
                # For file uploads, use a standalone request to avoid the client's
                # default Content-Type: application/json which prevents multipart encoding
                upload_headers = {"BV-API-KEY": self.api_key, "User-Agent": f"billionverify-python/{SDK_VERSION}"}
                response = httpx.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    files=files,
                    data=json,  # Form data for multipart
                    headers=upload_headers,
                    timeout=request_timeout,
                )
            elif skip_auth:
                response = httpx.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    json=json,
                    params=params,
                    headers=headers,
                    timeout=request_timeout,
                )
            else:
                response = self._client.request(
                    method=method,
                    url=path,
                    json=json,
                    params=params,
                    timeout=request_timeout,
                )
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            raise BillionVerifyError(f"Network error: {e}", "NETWORK_ERROR", 0)

        if response.status_code == 204:
            metadata = _response_metadata(response)
            return (None, metadata) if return_metadata else None

        if response.is_success:
            metadata = _response_metadata(response)
            result = response.json()
            # Extract data from API wrapper response {success, code, message, data}
            if isinstance(result, dict) and "data" in result:
                data = result["data"]
            else:
                data = result
            return (data, metadata) if return_metadata else data

        return self._handle_error(
            response, method, path, json, params, attempt, files, custom_timeout, skip_auth, return_metadata
        )

    def _request_raw(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        custom_timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Make an HTTP request and return the raw response (for file downloads)."""
        try:
            response = self._client.request(
                method=method,
                url=path,
                params=params,
                timeout=custom_timeout or self.timeout,
                follow_redirects=True,
            )
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            raise BillionVerifyError(f"Network error: {e}", "NETWORK_ERROR", 0)

        if response.is_success:
            return response

        self._handle_error(response, method, path, None, params, 1)
        # unreachable, _handle_error always raises
        raise BillionVerifyError("Unexpected error", "UNKNOWN_ERROR", 0)

    def _handle_error(
        self,
        response: httpx.Response,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]],
        params: Optional[Dict[str, Any]],
        attempt: int,
        files: Optional[Dict[str, Any]] = None,
        custom_timeout: Optional[float] = None,
        skip_auth: bool = False,
        return_metadata: bool = False,
    ) -> Any:
        """Handle error responses."""
        metadata = _response_metadata(response)
        try:
            data = response.json()
            error = data.get("error", {})
            message = error.get("message", response.reason_phrase)
            code = error.get("code", "UNKNOWN_ERROR")
            details = error.get("details")
        except Exception:
            message = response.reason_phrase
            code = "UNKNOWN_ERROR"
            details = None

        status = response.status_code

        if status == 401:
            raise AuthenticationError(message, response_metadata=metadata)

        if status == 402:
            raise InsufficientCreditsError(message, response_metadata=metadata)

        if status == 404:
            raise NotFoundError(message, response_metadata=metadata)

        if status == 429:
            retry_after = metadata.retry_after or 0
            if attempt < self.retries:
                time.sleep(retry_after or (2**attempt))
                return self._request(
                    method, path, json, params, attempt + 1, files, custom_timeout, skip_auth, return_metadata
                )
            raise RateLimitError(message, retry_after, response_metadata=metadata)

        if status == 400:
            raise ValidationError(message, details, response_metadata=metadata)

        if status in (500, 502, 503):
            if attempt < self.retries:
                time.sleep(2**attempt)
                return self._request(
                    method, path, json, params, attempt + 1, files, custom_timeout, skip_auth, return_metadata
                )

        raise BillionVerifyError(message, code, status, details, response_metadata=metadata)

    def health_check(self) -> HealthCheckResponse:
        """Check API health status (no authentication required).

        Returns:
            HealthCheckResponse with status information.
        """
        # Health check is at the root, not under /v1
        base_without_version = self.base_url.replace("/v1", "")
        try:
            response = httpx.get(
                f"{base_without_version}/health",
                timeout=self.timeout,
            )
            if response.is_success:
                data = response.json()
                return HealthCheckResponse(
                    status=data["status"],
                    version=data.get("version"),
                )
            raise BillionVerifyError("Health check failed", "HEALTH_CHECK_FAILED", response.status_code)
        except httpx.RequestError as e:
            raise BillionVerifyError(f"Network error: {e}", "NETWORK_ERROR", 0)

    def verify(
        self,
        email: str,
        check_smtp: bool = True,
        force_refresh: bool = False,
        include_domain_reputation: bool = False,
    ) -> VerificationResult:
        """Verify a single email address.

        Args:
            email: The email address to verify.
            check_smtp: Whether to perform SMTP verification (default: True).
            force_refresh: Whether to bypass cached results and force live verification (default: False).
            include_domain_reputation: Whether to include domain reputation details (default: False).

        Returns:
            VerificationResult with verification results.
        """
        payload: Dict[str, Any] = {
            "email": email,
            "check_smtp": check_smtp,
            "force_refresh": force_refresh,
            "include_domain_reputation": include_domain_reputation,
        }

        data, metadata = self._request("POST", "/verify/single", json=payload, return_metadata=True)

        return VerificationResult(
            email=data["email"],
            status=data["status"],
            score=data["score"],
            is_deliverable=data["is_deliverable"],
            is_disposable=data["is_disposable"],
            is_catchall=data["is_catchall"],
            is_role=data["is_role"],
            is_free=data["is_free"],
            domain=data["domain"],
            check_smtp=data.get("check_smtp", False),
            reason=data.get("reason", ""),
            response_time=data["response_time"],
            credits_used=data["credits_used"],
            domain_age=data.get("domain_age"),
            mx_records=data.get("mx_records", []),
            domain_reputation=DomainReputation(**data["domain_reputation"]) if data.get("domain_reputation") else None,
            domain_suggestion=data.get("domain_suggestion"),
            has_gravatar=data.get("has_gravatar", False),
            gravatar_url=data.get("gravatar_url"),
            smtp_response=data.get("smtp_response"),
            error_message=data.get("error_message"),
            response_metadata=metadata,
        )

    def verify_bulk(
        self,
        emails: List[str],
        check_smtp: bool = True,
    ) -> BulkVerifyResponse:
        """Verify multiple email addresses synchronously.

        Args:
            emails: List of email addresses to verify (max 50).
            check_smtp: Whether to perform SMTP verification (default: True).

        Returns:
            BulkVerifyResponse with verification results.
        """
        if len(emails) > 50:
            raise ValidationError("Maximum 50 emails per bulk request")

        payload: Dict[str, Any] = {"emails": emails, "check_smtp": check_smtp}

        data = self._request("POST", "/verify/bulk", json=payload)

        results = [
            BulkVerificationResult(
                email=item["email"],
                status=item["status"],
                score=item["score"],
                is_deliverable=item["is_deliverable"],
                is_disposable=item["is_disposable"],
                is_catchall=item["is_catchall"],
                is_role=item["is_role"],
                is_free=item["is_free"],
                domain=item["domain"],
                reason=item["reason"],
            )
            for item in data["results"]
        ]

        return BulkVerifyResponse(
            results=results,
            total_emails=data["total_emails"],
            valid_emails=data["valid_emails"],
            invalid_emails=data["invalid_emails"],
            credits_used=data["credits_used"],
            process_time=data["process_time"],
        )

    def verify_bulk_async(
        self,
        emails: List[str],
        check_smtp: bool = True,
    ) -> "BulkAsyncTaskResponse":
        """Sync counterpart to AsyncBillionVerify.verify_bulk_async."""
        if len(emails) < 51:
            raise ValidationError("verify_bulk_async requires at least 51 emails; use verify_bulk for ≤50")
        if len(emails) > 1000:
            raise ValidationError("verify_bulk_async accepts at most 1000 emails")

        from .types import BulkAsyncTaskResponse

        payload: Dict[str, Any] = {"emails": emails, "check_smtp": check_smtp}
        data = self._request("POST", "/verify/bulk", json=payload)

        return BulkAsyncTaskResponse(
            task_id=data["task_id"],
            status=data["status"],
            message=data.get("message", ""),
            status_url=data.get("status_url", f"/verify/file/{data['task_id']}"),
            created_at=data.get("created_at", ""),
            estimated_count=data.get("estimated_count", len(emails)),
            unique_emails=data.get("unique_emails"),
            total_emails=data.get("total_emails"),
        )

    def upload_file(
        self,
        file_path: str,
        check_smtp: bool = True,
        email_column: Optional[str] = None,
        preserve_original: bool = False,
    ) -> FileUploadResponse:
        """Upload a file for email verification.

        Args:
            file_path: Path to the CSV, Excel, or TXT file to upload.
            check_smtp: Whether to perform SMTP verification (default: True).
            email_column: Name of the column containing emails (for CSV files).
            preserve_original: Whether to preserve original columns in results (default: False).

        Returns:
            FileUploadResponse with task information.
        """
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            files = {"file": (path.name, f, "text/csv")}
            form_data: Dict[str, Any] = {"check_smtp": str(check_smtp).lower()}
            if email_column:
                form_data["email_column"] = email_column
            form_data["preserve_original"] = str(preserve_original).lower()

            data = self._request("POST", "/verify/file", json=form_data, files=files)

        return FileUploadResponse(
            task_id=data["task_id"],
            file_name=data["file_name"],
            file_size=data["file_size"],
            status=data["status"],
            message=data["message"],
            status_url=data["status_url"],
            created_at=data["created_at"],
            estimated_count=data["estimated_count"],
            unique_emails=data.get("unique_emails"),
            total_rows=data.get("total_rows"),
            email_column=data.get("email_column"),
        )

    def get_file_task_status(
        self,
        task_id: str,
        timeout: int = 0,
    ) -> FileTaskStatus:
        """Get the status of a file verification task.

        Args:
            task_id: The file task ID.
            timeout: Long-polling timeout in seconds (0-300). If > 0, the request
                     will wait up to this many seconds for the task to complete.

        Returns:
            FileTaskStatus with current task status.
        """
        params: Dict[str, Any] = {}
        if timeout > 0:
            if timeout > 300:
                raise ValidationError("Timeout must be between 0 and 300 seconds")
            params["timeout"] = timeout

        # Adjust request timeout for long-polling
        custom_timeout = self.timeout + timeout if timeout > 0 else None

        data = self._request("GET", f"/verify/file/{task_id}", params=params if params else None, custom_timeout=custom_timeout)

        return self._parse_file_task_status(data)

    def download_file_results(
        self,
        task_id: str,
        output_path: str,
        valid: Optional[bool] = None,
        invalid: Optional[bool] = None,
        catchall: Optional[bool] = None,
        role: Optional[bool] = None,
        unknown: Optional[bool] = None,
        disposable: Optional[bool] = None,
        risky: Optional[bool] = None,
    ) -> str:
        """Download the results of a completed file verification task as CSV.

        Args:
            task_id: The file task ID.
            output_path: Path to save the CSV file.
            valid: Include valid emails in results.
            invalid: Include invalid emails in results.
            catchall: Include catch-all emails in results.
            role: Include role-based emails in results.
            unknown: Include unknown emails in results.
            disposable: Include disposable emails in results.
            risky: Include risky emails in results.

        Returns:
            The path to the saved CSV file.
        """
        params: Dict[str, Any] = {}

        if valid is not None:
            params["valid"] = str(valid).lower()
        if invalid is not None:
            params["invalid"] = str(invalid).lower()
        if catchall is not None:
            params["catchall"] = str(catchall).lower()
        if role is not None:
            params["role"] = str(role).lower()
        if unknown is not None:
            params["unknown"] = str(unknown).lower()
        if disposable is not None:
            params["disposable"] = str(disposable).lower()
        if risky is not None:
            params["risky"] = str(risky).lower()

        response = self._request_raw("GET", f"/verify/file/{task_id}/results", params=params if params else None)

        out = Path(output_path)
        out.write_bytes(response.content)
        return str(out)

    def download_bulk_results(
        self,
        task_id: str,
        output_path: str,
        valid: Optional[bool] = None,
        invalid: Optional[bool] = None,
        catchall: Optional[bool] = None,
        role: Optional[bool] = None,
        unknown: Optional[bool] = None,
        disposable: Optional[bool] = None,
        risky: Optional[bool] = None,
    ) -> str:
        """Download bulk async results CSV. Backend reuses /verify/file/:task_id/results."""
        params: Dict[str, Any] = {}
        for name, val in (("valid", valid), ("invalid", invalid), ("catchall", catchall),
                          ("role", role), ("unknown", unknown), ("disposable", disposable),
                          ("risky", risky)):
            if val is not None:
                params[name] = str(val).lower()
        response = self._request_raw(
            "GET", f"/verify/file/{task_id}/results",
            params=params if params else None,
        )
        out = Path(output_path)
        out.write_bytes(response.content)
        return str(out)

    def wait_for_file_task(
        self,
        task_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ) -> FileTaskStatus:
        """Poll for file task completion.

        Args:
            task_id: The file task ID.
            poll_interval: Time between polls in seconds (default: 5).
            max_wait: Maximum wait time in seconds (default: 600).

        Returns:
            FileTaskStatus when task completes.

        Raises:
            TimeoutError: If task doesn't complete within max_wait.
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = self.get_file_task_status(task_id)

            if status.status in ("completed", "failed"):
                return status

            time.sleep(poll_interval)

        raise TimeoutError(f"File task {task_id} did not complete within {max_wait}s")

    def get_bulk_task_status(self, task_id: str, timeout: int = 0) -> "BulkTaskStatus":
        """Poll a bulk async task. Backend reuses /verify/file/:task_id."""
        from .types import BulkTaskStatus

        params: Dict[str, Any] = {}
        if timeout > 0:
            if timeout > 300:
                raise ValidationError("Timeout must be between 0 and 300 seconds")
            params["timeout"] = timeout
        custom_timeout = self.timeout + timeout if timeout > 0 else None
        data = self._request(
            "GET", f"/verify/file/{task_id}",
            params=params if params else None,
            custom_timeout=custom_timeout,
        )
        valid_fields = set(BulkTaskStatus.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in data.items() if k in valid_fields}
        try:
            return BulkTaskStatus(**kwargs)
        except TypeError as e:
            raise BillionVerifyError(
                f"bulk task status response missing required fields: {e}",
                "INVALID_RESPONSE",
                0,
            ) from e

    def get_credits(self) -> CreditsResponse:
        """Get current credit balance.

        Returns:
            CreditsResponse with credit information.
        """
        data = self._request("GET", "/credits")

        return CreditsResponse(
            account_id=data["account_id"],
            api_key_id=data["api_key_id"],
            api_key_name=data["api_key_name"],
            credits_balance=data["credits_balance"],
            credits_consumed=data["credits_consumed"],
            credits_added=data["credits_added"],
            last_updated=data["last_updated"],
        )

    def create_webhook(
        self,
        url: str,
        events: List[WebhookEvent],
    ) -> Webhook:
        """Create a new webhook.

        Args:
            url: The webhook URL.
            events: List of events to subscribe to.

        Returns:
            Webhook configuration (includes secret on creation).
        """
        payload: Dict[str, Any] = {"url": url, "events": events}

        data = self._request("POST", "/webhooks", json=payload)

        return Webhook(
            id=data["id"],
            url=data["url"],
            events=data["events"],
            secret=data.get("secret"),
            is_active=data["is_active"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def list_webhooks(self) -> List[Webhook]:
        """List all webhooks.

        Returns:
            List of Webhook configurations.
        """
        data = self._request("GET", "/webhooks")

        return [
            Webhook(
                id=item["id"],
                url=item["url"],
                events=item["events"],
                secret=item.get("secret"),
                is_active=item["is_active"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )
            for item in data
        ]

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook.

        Args:
            webhook_id: The webhook ID to delete.
        """
        self._request("DELETE", f"/webhooks/{webhook_id}")

    @staticmethod
    def verify_webhook_signature(
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify a webhook signature.

        Args:
            payload: The raw request body.
            signature: The signature from the request header.
            secret: Your webhook secret.

        Returns:
            True if signature is valid.
        """
        expected = f"sha256={hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(signature, expected)

    @staticmethod
    def _parse_file_task_status(data: Dict[str, Any]) -> FileTaskStatus:
        """Parse file task status response into FileTaskStatus."""
        return FileTaskStatus(
            task_id=data["task_id"],
            status=data["status"],
            progress=data.get("progress", 0),
            total_emails=data.get("total_emails", 0),
            processed_emails=data.get("processed_emails", 0),
            valid_emails=data.get("valid_emails", 0),
            invalid_emails=data.get("invalid_emails", 0),
            unknown_emails=data.get("unknown_emails", 0),
            credits_used=data.get("credits_used", 0),
            risky_emails=data.get("risky_emails", 0),
            disposable_emails=data.get("disposable_emails", 0),
            role_emails=data.get("role_emails", 0),
            catchall_emails=data.get("catchall_emails", 0),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error_message=data.get("error_message"),
            download_url=data.get("download_url"),
            direct_download_url=data.get("direct_download_url"),
            direct_download_expires_at=data.get("direct_download_expires_at"),
            can_pause=data.get("can_pause", False),
            can_resume=data.get("can_resume", False),
            can_restart=data.get("can_restart", False),
            total_chunks=data.get("total_chunks"),
            completed_chunks=data.get("completed_chunks"),
            failed_chunks=data.get("failed_chunks"),
            unique_emails=data.get("unique_emails"),
            total_rows=data.get("total_rows"),
        )


class AsyncBillionVerify:
    """Async BillionVerify API Client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        """Initialize the async BillionVerify client."""
        if not api_key:
            raise AuthenticationError("API key is required")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "BV-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": f"billionverify-python/{SDK_VERSION}",
            },
        )

    async def __aenter__(self) -> "AsyncBillionVerify":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        attempt: int = 1,
        files: Optional[Dict[str, Any]] = None,
        custom_timeout: Optional[float] = None,
        skip_auth: bool = False,
        return_metadata: bool = False,
    ) -> Any:
        """Make an async HTTP request to the API."""
        try:
            headers = {}
            if skip_auth:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": f"billionverify-python/{SDK_VERSION}",
                }

            request_timeout = custom_timeout if custom_timeout else self.timeout

            if files:
                # For file uploads, use a standalone client to avoid the default
                # Content-Type: application/json which prevents multipart encoding
                upload_headers = {"BV-API-KEY": self.api_key, "User-Agent": f"billionverify-python/{SDK_VERSION}"}
                async with httpx.AsyncClient() as upload_client:
                    response = await upload_client.request(
                        method=method,
                        url=f"{self.base_url}{path}",
                        files=files,
                        data=json,
                        headers=upload_headers,
                        timeout=request_timeout,
                    )
            elif skip_auth:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=method,
                        url=f"{self.base_url}{path}",
                        json=json,
                        params=params,
                        headers=headers,
                        timeout=request_timeout,
                    )
            else:
                response = await self._client.request(
                    method=method,
                    url=path,
                    json=json,
                    params=params,
                    timeout=request_timeout,
                )
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            raise BillionVerifyError(f"Network error: {e}", "NETWORK_ERROR", 0)

        if response.status_code == 204:
            metadata = _response_metadata(response)
            return (None, metadata) if return_metadata else None

        if response.is_success:
            metadata = _response_metadata(response)
            result = response.json()
            # Extract data from API wrapper response {success, code, message, data}
            if isinstance(result, dict) and "data" in result:
                data = result["data"]
            else:
                data = result
            return (data, metadata) if return_metadata else data

        return await self._handle_error(
            response, method, path, json, params, attempt, files, custom_timeout, skip_auth, return_metadata
        )

    async def _request_raw(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        custom_timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Make an async HTTP request and return the raw response (for file downloads)."""
        try:
            response = await self._client.request(
                method=method,
                url=path,
                params=params,
                timeout=custom_timeout or self.timeout,
                follow_redirects=True,
            )
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            raise BillionVerifyError(f"Network error: {e}", "NETWORK_ERROR", 0)

        if response.is_success:
            return response

        await self._handle_error(response, method, path, None, params, 1)
        raise BillionVerifyError("Unexpected error", "UNKNOWN_ERROR", 0)

    async def _handle_error(
        self,
        response: httpx.Response,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]],
        params: Optional[Dict[str, Any]],
        attempt: int,
        files: Optional[Dict[str, Any]] = None,
        custom_timeout: Optional[float] = None,
        skip_auth: bool = False,
        return_metadata: bool = False,
    ) -> Any:
        """Handle error responses."""
        import asyncio

        metadata = _response_metadata(response)
        try:
            data = response.json()
            error = data.get("error", {})
            message = error.get("message", response.reason_phrase)
            code = error.get("code", "UNKNOWN_ERROR")
            details = error.get("details")
        except Exception:
            message = response.reason_phrase
            code = "UNKNOWN_ERROR"
            details = None

        status = response.status_code

        if status == 401:
            raise AuthenticationError(message, response_metadata=metadata)

        if status == 402:
            raise InsufficientCreditsError(message, response_metadata=metadata)

        if status == 404:
            raise NotFoundError(message, response_metadata=metadata)

        if status == 429:
            retry_after = metadata.retry_after or 0
            if attempt < self.retries:
                await asyncio.sleep(retry_after or (2**attempt))
                return await self._request(
                    method, path, json, params, attempt + 1, files, custom_timeout, skip_auth, return_metadata
                )
            raise RateLimitError(message, retry_after, response_metadata=metadata)

        if status == 400:
            raise ValidationError(message, details, response_metadata=metadata)

        if status in (500, 502, 503):
            if attempt < self.retries:
                await asyncio.sleep(2**attempt)
                return await self._request(
                    method, path, json, params, attempt + 1, files, custom_timeout, skip_auth, return_metadata
                )

        raise BillionVerifyError(message, code, status, details, response_metadata=metadata)

    async def health_check(self) -> HealthCheckResponse:
        """Check API health status (no authentication required)."""
        base_without_version = self.base_url.replace("/v1", "")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_without_version}/health",
                    timeout=self.timeout,
                )
                if response.is_success:
                    data = response.json()
                    return HealthCheckResponse(
                        status=data["status"],
                        version=data.get("version"),
                    )
                raise BillionVerifyError("Health check failed", "HEALTH_CHECK_FAILED", response.status_code)
        except httpx.RequestError as e:
            raise BillionVerifyError(f"Network error: {e}", "NETWORK_ERROR", 0)

    async def verify(
        self,
        email: str,
        check_smtp: bool = True,
        force_refresh: bool = False,
        include_domain_reputation: bool = False,
    ) -> VerificationResult:
        """Verify a single email address."""
        payload: Dict[str, Any] = {
            "email": email,
            "check_smtp": check_smtp,
            "force_refresh": force_refresh,
            "include_domain_reputation": include_domain_reputation,
        }

        data, metadata = await self._request("POST", "/verify/single", json=payload, return_metadata=True)

        return VerificationResult(
            email=data["email"],
            status=data["status"],
            score=data["score"],
            is_deliverable=data["is_deliverable"],
            is_disposable=data["is_disposable"],
            is_catchall=data["is_catchall"],
            is_role=data["is_role"],
            is_free=data["is_free"],
            domain=data["domain"],
            check_smtp=data.get("check_smtp", False),
            reason=data.get("reason", ""),
            response_time=data["response_time"],
            credits_used=data["credits_used"],
            domain_age=data.get("domain_age"),
            mx_records=data.get("mx_records", []),
            domain_reputation=DomainReputation(**data["domain_reputation"]) if data.get("domain_reputation") else None,
            domain_suggestion=data.get("domain_suggestion"),
            has_gravatar=data.get("has_gravatar", False),
            gravatar_url=data.get("gravatar_url"),
            smtp_response=data.get("smtp_response"),
            error_message=data.get("error_message"),
            response_metadata=metadata,
        )

    async def verify_bulk(
        self,
        emails: List[str],
        check_smtp: bool = True,
    ) -> BulkVerifyResponse:
        """Verify multiple email addresses synchronously."""
        if len(emails) > 50:
            raise ValidationError("Maximum 50 emails per bulk request")

        payload: Dict[str, Any] = {"emails": emails, "check_smtp": check_smtp}

        data = await self._request("POST", "/verify/bulk", json=payload)

        results = [
            BulkVerificationResult(
                email=item["email"],
                status=item["status"],
                score=item["score"],
                is_deliverable=item["is_deliverable"],
                is_disposable=item["is_disposable"],
                is_catchall=item["is_catchall"],
                is_role=item["is_role"],
                is_free=item["is_free"],
                domain=item["domain"],
                reason=item["reason"],
            )
            for item in data["results"]
        ]

        return BulkVerifyResponse(
            results=results,
            total_emails=data["total_emails"],
            valid_emails=data["valid_emails"],
            invalid_emails=data["invalid_emails"],
            credits_used=data["credits_used"],
            process_time=data["process_time"],
        )

    async def verify_bulk_async(
        self,
        emails: List[str],
        check_smtp: bool = True,
    ) -> "BulkAsyncTaskResponse":
        """Submit a 51-1000 email batch via the async bulk endpoint.

        For batches of 50 or fewer emails, use ``verify_bulk`` instead.
        """
        if len(emails) < 51:
            raise ValidationError("verify_bulk_async requires at least 51 emails; use verify_bulk for ≤50")
        if len(emails) > 1000:
            raise ValidationError("verify_bulk_async accepts at most 1000 emails")

        from .types import BulkAsyncTaskResponse

        payload: Dict[str, Any] = {"emails": emails, "check_smtp": check_smtp}
        data = await self._request("POST", "/verify/bulk", json=payload)

        return BulkAsyncTaskResponse(
            task_id=data["task_id"],
            status=data["status"],
            message=data.get("message", ""),
            status_url=data.get("status_url", f"/verify/file/{data['task_id']}"),
            created_at=data.get("created_at", ""),
            estimated_count=data.get("estimated_count", len(emails)),
            unique_emails=data.get("unique_emails"),
            total_emails=data.get("total_emails"),
        )

    async def upload_file(
        self,
        file_path: str,
        check_smtp: bool = True,
        email_column: Optional[str] = None,
        preserve_original: bool = False,
    ) -> FileUploadResponse:
        """Upload a file for email verification."""
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            files = {"file": (path.name, f.read(), "text/csv")}
            form_data: Dict[str, Any] = {"check_smtp": str(check_smtp).lower()}
            if email_column:
                form_data["email_column"] = email_column
            form_data["preserve_original"] = str(preserve_original).lower()

            data = await self._request("POST", "/verify/file", json=form_data, files=files)

        return FileUploadResponse(
            task_id=data["task_id"],
            file_name=data["file_name"],
            file_size=data["file_size"],
            status=data["status"],
            message=data["message"],
            status_url=data["status_url"],
            created_at=data["created_at"],
            estimated_count=data["estimated_count"],
            unique_emails=data.get("unique_emails"),
            total_rows=data.get("total_rows"),
            email_column=data.get("email_column"),
        )

    async def get_file_task_status(
        self,
        task_id: str,
        timeout: int = 0,
    ) -> FileTaskStatus:
        """Get the status of a file verification task."""
        params: Dict[str, Any] = {}
        if timeout > 0:
            if timeout > 300:
                raise ValidationError("Timeout must be between 0 and 300 seconds")
            params["timeout"] = timeout

        custom_timeout = self.timeout + timeout if timeout > 0 else None

        data = await self._request("GET", f"/verify/file/{task_id}", params=params if params else None, custom_timeout=custom_timeout)

        return BillionVerify._parse_file_task_status(data)

    async def download_file_results(
        self,
        task_id: str,
        output_path: str,
        valid: Optional[bool] = None,
        invalid: Optional[bool] = None,
        catchall: Optional[bool] = None,
        role: Optional[bool] = None,
        unknown: Optional[bool] = None,
        disposable: Optional[bool] = None,
        risky: Optional[bool] = None,
    ) -> str:
        """Download the results of a completed file verification task as CSV."""
        params: Dict[str, Any] = {}

        if valid is not None:
            params["valid"] = str(valid).lower()
        if invalid is not None:
            params["invalid"] = str(invalid).lower()
        if catchall is not None:
            params["catchall"] = str(catchall).lower()
        if role is not None:
            params["role"] = str(role).lower()
        if unknown is not None:
            params["unknown"] = str(unknown).lower()
        if disposable is not None:
            params["disposable"] = str(disposable).lower()
        if risky is not None:
            params["risky"] = str(risky).lower()

        response = await self._request_raw("GET", f"/verify/file/{task_id}/results", params=params if params else None)

        out = Path(output_path)
        out.write_bytes(response.content)
        return str(out)

    async def download_bulk_results(
        self,
        task_id: str,
        output_path: str,
        valid: Optional[bool] = None,
        invalid: Optional[bool] = None,
        catchall: Optional[bool] = None,
        role: Optional[bool] = None,
        unknown: Optional[bool] = None,
        disposable: Optional[bool] = None,
        risky: Optional[bool] = None,
    ) -> str:
        """Download bulk async results CSV. Backend reuses /verify/file/:task_id/results."""
        params: Dict[str, Any] = {}
        for name, val in (("valid", valid), ("invalid", invalid), ("catchall", catchall),
                          ("role", role), ("unknown", unknown), ("disposable", disposable),
                          ("risky", risky)):
            if val is not None:
                params[name] = str(val).lower()
        response = await self._request_raw(
            "GET", f"/verify/file/{task_id}/results",
            params=params if params else None,
        )
        out = Path(output_path)
        out.write_bytes(response.content)
        return str(out)

    async def wait_for_file_task(
        self,
        task_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ) -> FileTaskStatus:
        """Poll for file task completion."""
        import asyncio

        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = await self.get_file_task_status(task_id)

            if status.status in ("completed", "failed"):
                return status

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"File task {task_id} did not complete within {max_wait}s")

    async def get_bulk_task_status(self, task_id: str, timeout: int = 0) -> "BulkTaskStatus":
        """Poll a bulk async task. Backend reuses /verify/file/:task_id."""
        from .types import BulkTaskStatus

        params: Dict[str, Any] = {}
        if timeout > 0:
            if timeout > 300:
                raise ValidationError("Timeout must be between 0 and 300 seconds")
            params["timeout"] = timeout
        custom_timeout = self.timeout + timeout if timeout > 0 else None
        data = await self._request(
            "GET", f"/verify/file/{task_id}",
            params=params if params else None,
            custom_timeout=custom_timeout,
        )
        valid_fields = set(BulkTaskStatus.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in data.items() if k in valid_fields}
        try:
            return BulkTaskStatus(**kwargs)
        except TypeError as e:
            raise BillionVerifyError(
                f"bulk task status response missing required fields: {e}",
                "INVALID_RESPONSE",
                0,
            ) from e

    async def get_credits(self) -> CreditsResponse:
        """Get current credit balance."""
        data = await self._request("GET", "/credits")

        return CreditsResponse(
            account_id=data["account_id"],
            api_key_id=data["api_key_id"],
            api_key_name=data["api_key_name"],
            credits_balance=data["credits_balance"],
            credits_consumed=data["credits_consumed"],
            credits_added=data["credits_added"],
            last_updated=data["last_updated"],
        )

    async def create_webhook(
        self,
        url: str,
        events: List[WebhookEvent],
    ) -> Webhook:
        """Create a new webhook."""
        payload: Dict[str, Any] = {"url": url, "events": events}

        data = await self._request("POST", "/webhooks", json=payload)

        return Webhook(
            id=data["id"],
            url=data["url"],
            events=data["events"],
            secret=data.get("secret"),
            is_active=data["is_active"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    async def list_webhooks(self) -> List[Webhook]:
        """List all webhooks."""
        data = await self._request("GET", "/webhooks")

        return [
            Webhook(
                id=item["id"],
                url=item["url"],
                events=item["events"],
                secret=item.get("secret"),
                is_active=item["is_active"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )
            for item in data
        ]

    async def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook."""
        await self._request("DELETE", f"/webhooks/{webhook_id}")

    @staticmethod
    def verify_webhook_signature(
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify a webhook signature."""
        expected = f"sha256={hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(signature, expected)
