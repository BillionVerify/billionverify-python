"""BillionVerify SDK Client."""

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
    FileJobResponse,
    FileResultItem,
    FileResultsResponse,
    HealthCheckResponse,
    VerificationResult,
    VerificationStatus,
    Webhook,
    WebhookEvent,
)

DEFAULT_BASE_URL = "https://api.billionverify.com/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3


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
                "EV-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "billionverify-python/1.0.0",
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
    ) -> Any:
        """Make an HTTP request to the API."""
        try:
            headers = {}
            if skip_auth:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "billionverify-python/1.0.0",
                }

            request_timeout = custom_timeout if custom_timeout else self.timeout

            if files:
                # For file uploads, remove Content-Type header to let httpx set it
                upload_headers = {"EV-API-KEY": self.api_key, "User-Agent": "billionverify-python/1.0.0"}
                response = self._client.request(
                    method=method,
                    url=path,
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
            return None

        if response.is_success:
            result = response.json()
            # Extract data from API wrapper response {success, code, message, data}
            if isinstance(result, dict) and "data" in result:
                return result["data"]
            return result

        self._handle_error(response, method, path, json, params, attempt, files, custom_timeout, skip_auth)

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
    ) -> None:
        """Handle error responses."""
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
            raise AuthenticationError(message)

        if status == 402:
            raise InsufficientCreditsError(message)

        if status == 404:
            raise NotFoundError(message)

        if status == 429:
            retry_after = int(response.headers.get("Retry-After", "0"))
            if attempt < self.retries:
                time.sleep(retry_after or (2**attempt))
                return self._request(method, path, json, params, attempt + 1, files, custom_timeout, skip_auth)
            raise RateLimitError(message, retry_after)

        if status == 400:
            raise ValidationError(message, details)

        if status in (500, 502, 503):
            if attempt < self.retries:
                time.sleep(2**attempt)
                return self._request(method, path, json, params, attempt + 1, files, custom_timeout, skip_auth)

        raise BillionVerifyError(message, code, status, details)

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
    ) -> VerificationResult:
        """Verify a single email address.

        Args:
            email: The email address to verify.
            check_smtp: Whether to perform SMTP verification (default: True).

        Returns:
            VerificationResult with verification results.
        """
        payload: Dict[str, Any] = {"email": email, "check_smtp": check_smtp}

        data = self._request("POST", "/verify/single", json=payload)

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
            domain_age=data.get("domain_age"),
            mx_records=data.get("mx_records", []),
            domain_reputation=DomainReputation(**data["domain_reputation"]) if data.get("domain_reputation") else None,
            smtp_check=data["smtp_check"],
            reason=data["reason"],
            suggestion=data.get("suggestion"),
            response_time=data["response_time"],
            credits_used=data["credits_used"],
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

    def upload_file(
        self,
        file_path: str,
        check_smtp: bool = True,
        email_column: Optional[str] = None,
        preserve_original: bool = False,
    ) -> FileJobResponse:
        """Upload a file for email verification.

        Args:
            file_path: Path to the CSV or TXT file to upload.
            check_smtp: Whether to perform SMTP verification (default: True).
            email_column: Name of the column containing emails (for CSV files).
            preserve_original: Whether to preserve original columns in results (default: False).

        Returns:
            FileJobResponse with job information.
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

        return FileJobResponse(
            job_id=data["job_id"],
            status=data["status"],
            total=data["total"],
            processed=data["processed"],
            valid=data["valid"],
            invalid=data["invalid"],
            unknown=data["unknown"],
            credits_used=data["credits_used"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
            progress_percent=data.get("progress_percent"),
            filename=data.get("filename"),
        )

    def get_file_job_status(
        self,
        job_id: str,
        timeout: int = 0,
    ) -> FileJobResponse:
        """Get the status of a file verification job.

        Args:
            job_id: The file job ID.
            timeout: Long-polling timeout in seconds (0-300). If > 0, the request
                     will wait up to this many seconds for the job to complete.

        Returns:
            FileJobResponse with current job status.
        """
        params: Dict[str, Any] = {}
        if timeout > 0:
            if timeout > 300:
                raise ValidationError("Timeout must be between 0 and 300 seconds")
            params["timeout"] = timeout

        # Adjust request timeout for long-polling
        custom_timeout = self.timeout + timeout if timeout > 0 else None

        data = self._request("GET", f"/verify/file/{job_id}", params=params if params else None, custom_timeout=custom_timeout)

        return FileJobResponse(
            job_id=data["job_id"],
            status=data["status"],
            total=data["total"],
            processed=data["processed"],
            valid=data["valid"],
            invalid=data["invalid"],
            unknown=data["unknown"],
            credits_used=data["credits_used"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
            progress_percent=data.get("progress_percent"),
            filename=data.get("filename"),
        )

    def get_file_job_results(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
        valid: Optional[bool] = None,
        invalid: Optional[bool] = None,
        catchall: Optional[bool] = None,
        role: Optional[bool] = None,
        unknown: Optional[bool] = None,
        disposable: Optional[bool] = None,
        risky: Optional[bool] = None,
    ) -> FileResultsResponse:
        """Get the results of a completed file verification job.

        Args:
            job_id: The file job ID.
            limit: Number of results per page (default: 100, max: 1000).
            offset: Starting position (default: 0).
            valid: Include valid emails in results.
            invalid: Include invalid emails in results.
            catchall: Include catch-all emails in results.
            role: Include role-based emails in results.
            unknown: Include unknown emails in results.
            disposable: Include disposable emails in results.
            risky: Include risky emails in results.

        Returns:
            FileResultsResponse with verification results.
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        # Add filter parameters
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

        data = self._request("GET", f"/verify/file/{job_id}/results", params=params)

        results = [
            FileResultItem(
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
                original_row=item.get("original_row"),
            )
            for item in data["results"]
        ]

        return FileResultsResponse(
            job_id=data["job_id"],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
            results=results,
        )

    def wait_for_file_job(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ) -> FileJobResponse:
        """Poll for file job completion.

        Args:
            job_id: The file job ID.
            poll_interval: Time between polls in seconds (default: 5).
            max_wait: Maximum wait time in seconds (default: 600).

        Returns:
            FileJobResponse when job completes.

        Raises:
            TimeoutError: If job doesn't complete within max_wait.
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = self.get_file_job_status(job_id)

            if status.status in ("completed", "failed"):
                return status

            time.sleep(poll_interval)

        raise TimeoutError(f"File job {job_id} did not complete within {max_wait}s")

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
                "EV-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "billionverify-python/1.0.0",
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
    ) -> Any:
        """Make an async HTTP request to the API."""
        import asyncio

        try:
            headers = {}
            if skip_auth:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "billionverify-python/1.0.0",
                }

            request_timeout = custom_timeout if custom_timeout else self.timeout

            if files:
                upload_headers = {"EV-API-KEY": self.api_key, "User-Agent": "billionverify-python/1.0.0"}
                response = await self._client.request(
                    method=method,
                    url=path,
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
            return None

        if response.is_success:
            return response.json()

        await self._handle_error(response, method, path, json, params, attempt, files, custom_timeout, skip_auth)

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
    ) -> None:
        """Handle error responses."""
        import asyncio

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
            raise AuthenticationError(message)

        if status == 402:
            raise InsufficientCreditsError(message)

        if status == 404:
            raise NotFoundError(message)

        if status == 429:
            retry_after = int(response.headers.get("Retry-After", "0"))
            if attempt < self.retries:
                await asyncio.sleep(retry_after or (2**attempt))
                return await self._request(method, path, json, params, attempt + 1, files, custom_timeout, skip_auth)
            raise RateLimitError(message, retry_after)

        if status == 400:
            raise ValidationError(message, details)

        if status in (500, 502, 503):
            if attempt < self.retries:
                await asyncio.sleep(2**attempt)
                return await self._request(method, path, json, params, attempt + 1, files, custom_timeout, skip_auth)

        raise BillionVerifyError(message, code, status, details)

    async def health_check(self) -> HealthCheckResponse:
        """Check API health status (no authentication required).

        Returns:
            HealthCheckResponse with status information.
        """
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
    ) -> VerificationResult:
        """Verify a single email address."""
        payload: Dict[str, Any] = {"email": email, "check_smtp": check_smtp}

        data = await self._request("POST", "/verify/single", json=payload)

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
            domain_age=data.get("domain_age"),
            mx_records=data.get("mx_records", []),
            domain_reputation=DomainReputation(**data["domain_reputation"]) if data.get("domain_reputation") else None,
            smtp_check=data["smtp_check"],
            reason=data["reason"],
            suggestion=data.get("suggestion"),
            response_time=data["response_time"],
            credits_used=data["credits_used"],
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

    async def upload_file(
        self,
        file_path: str,
        check_smtp: bool = True,
        email_column: Optional[str] = None,
        preserve_original: bool = False,
    ) -> FileJobResponse:
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

        return FileJobResponse(
            job_id=data["job_id"],
            status=data["status"],
            total=data["total"],
            processed=data["processed"],
            valid=data["valid"],
            invalid=data["invalid"],
            unknown=data["unknown"],
            credits_used=data["credits_used"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
            progress_percent=data.get("progress_percent"),
            filename=data.get("filename"),
        )

    async def get_file_job_status(
        self,
        job_id: str,
        timeout: int = 0,
    ) -> FileJobResponse:
        """Get the status of a file verification job."""
        params: Dict[str, Any] = {}
        if timeout > 0:
            if timeout > 300:
                raise ValidationError("Timeout must be between 0 and 300 seconds")
            params["timeout"] = timeout

        custom_timeout = self.timeout + timeout if timeout > 0 else None

        data = await self._request("GET", f"/verify/file/{job_id}", params=params if params else None, custom_timeout=custom_timeout)

        return FileJobResponse(
            job_id=data["job_id"],
            status=data["status"],
            total=data["total"],
            processed=data["processed"],
            valid=data["valid"],
            invalid=data["invalid"],
            unknown=data["unknown"],
            credits_used=data["credits_used"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
            progress_percent=data.get("progress_percent"),
            filename=data.get("filename"),
        )

    async def get_file_job_results(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
        valid: Optional[bool] = None,
        invalid: Optional[bool] = None,
        catchall: Optional[bool] = None,
        role: Optional[bool] = None,
        unknown: Optional[bool] = None,
        disposable: Optional[bool] = None,
        risky: Optional[bool] = None,
    ) -> FileResultsResponse:
        """Get the results of a completed file verification job."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

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

        data = await self._request(
            "GET", f"/verify/file/{job_id}/results", params=params
        )

        results = [
            FileResultItem(
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
                original_row=item.get("original_row"),
            )
            for item in data["results"]
        ]

        return FileResultsResponse(
            job_id=data["job_id"],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
            results=results,
        )

    async def wait_for_file_job(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ) -> FileJobResponse:
        """Poll for file job completion."""
        import asyncio

        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = await self.get_file_job_status(job_id)

            if status.status in ("completed", "failed"):
                return status

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"File job {job_id} did not complete within {max_wait}s")

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
