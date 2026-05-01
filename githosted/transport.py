"""httpx-based Connect unary HTTP+JSON transport.

Each RPC is a POST to ``{base_url}/githosted.v1.{service}/{method}`` with a
JSON body matching the protobuf JSON mapping (camelCase field names, base64
for bytes, RFC 3339 for timestamps).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from .errors import ConnectError


class ConnectTransport:
    """Sync HTTP+JSON transport for Connect unary RPCs."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        client_name: str = "sdk-python",
        on_telemetry: Any | None = None,
    ) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=30.0,
        )
        self._client_name = client_name.strip().lower() or "sdk-python"
        self._on_telemetry = on_telemetry

    def call(
        self, service: str, method: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a unary Connect RPC call.

        Raises ``ConnectError`` on non-200 responses with a parseable Connect
        error body.  Falls back to a generic ``ConnectError`` if the response
        body cannot be parsed.
        """
        url = f"/githosted.v1.{service}/{method}"
        request_id = f"req_{uuid.uuid4()}"
        started_at = time.time()
        response = self._client.post(
            url,
            json=request,
            headers={
                "X-Request-Id": request_id,
                "X-Githosted-Client": self._client_name,
            },
        )

        if response.status_code != 200:
            self._emit(
                request_id=request_id,
                procedure=url,
                duration_ms=int((time.time() - started_at) * 1000),
                outcome="error",
                error_message=response.text,
            )
            try:
                body = response.json()
            except Exception:
                raise ConnectError(
                    code="unknown",
                    message=f"HTTP {response.status_code}: {response.text}",
                )
            raise ConnectError(
                code=body.get("code", "unknown"),
                message=body.get("message", ""),
                details=body.get("details"),
            )

        if not response.content:
            self._emit(
                request_id=request_id,
                procedure=url,
                duration_ms=int((time.time() - started_at) * 1000),
                outcome="ok",
            )
            return {}
        self._emit(
            request_id=request_id,
            procedure=url,
            duration_ms=int((time.time() - started_at) * 1000),
            outcome="ok",
        )
        return response.json()

    def close(self) -> None:
        self._client.close()

    def _emit(
        self,
        *,
        request_id: str,
        procedure: str,
        duration_ms: int,
        outcome: str,
        error_message: str | None = None,
    ) -> None:
        if self._on_telemetry is None:
            return
        payload: dict[str, Any] = {
            "request_id": request_id,
            "client_name": self._client_name,
            "procedure": procedure,
            "duration_ms": duration_ms,
            "outcome": outcome,
        }
        if error_message:
            payload["error_message"] = error_message
        self._on_telemetry(payload)
