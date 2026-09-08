"""Shared, deliberately small HTTP discipline for provider adapters."""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from ..models import CoreError, ErrorCode


MAX_RESPONSE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class _TransportResponse:
    status_code: int
    retry_after: str | None
    payload: dict[str, Any] | None


class ProviderTransport:
    """Make one bounded JSON request, with at most one safe retry."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._monotonic = monotonic
        self._sleep = sleep

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        request_id: str,
        headers: Mapping[str, str],
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
        deadline: float,
    ) -> dict[str, Any]:
        for attempt in range(2):
            try:
                response = await self._request_once(
                    method,
                    url,
                    request_id=request_id,
                    headers=headers,
                    params=params,
                    json_body=json_body,
                    deadline=deadline,
                )
            except httpx.ConnectError:
                if attempt == 0 and await self._wait_to_retry(None, deadline):
                    continue
                raise CoreError(request_id, ErrorCode.NETWORK_ERROR) from None
            except (httpx.ReadTimeout, httpx.ReadError, httpx.TimeoutException, httpx.NetworkError):
                raise CoreError(request_id, ErrorCode.NETWORK_ERROR) from None
            except httpx.HTTPError:
                raise CoreError(request_id, ErrorCode.NETWORK_ERROR) from None

            if response.status_code < 400:
                assert response.payload is not None
                return response.payload

            code = self._status_code(response.status_code)
            if attempt == 0 and (response.status_code == 429 or response.status_code >= 500):
                if await self._wait_to_retry(response.retry_after, deadline):
                    continue
            raise CoreError(request_id, code)

        raise CoreError(request_id, ErrorCode.NETWORK_ERROR)

    async def _request_once(
        self,
        method: str,
        url: str,
        *,
        request_id: str,
        headers: Mapping[str, str],
        params: Mapping[str, str] | None,
        json_body: Mapping[str, Any] | None,
        deadline: float,
    ) -> _TransportResponse:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise httpx.ReadTimeout("provider deadline elapsed")
        timeout = httpx.Timeout(remaining, connect=min(5.0, remaining))
        async with self._client.stream(
            method, url, headers=headers, params=params, json=json_body, timeout=timeout
        ) as response:
            if response.status_code >= 400:
                return _TransportResponse(response.status_code, response.headers.get("retry-after"), None)
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                if deadline - self._monotonic() <= 0:
                    raise httpx.ReadTimeout("provider deadline elapsed")
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
                chunks.append(chunk)
                if deadline - self._monotonic() <= 0:
                    raise httpx.ReadTimeout("provider deadline elapsed")
            if deadline - self._monotonic() <= 0:
                raise httpx.ReadTimeout("provider deadline elapsed")
        try:
            value = json.loads(b"".join(chunks))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR) from None
        if not isinstance(value, dict):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return _TransportResponse(200, None, value)

    async def _wait_to_retry(self, retry_after: str | None, deadline: float) -> bool:
        remaining = deadline - self._monotonic()
        maximum_wait = remaining - 1.0
        if maximum_wait <= 0:
            return False
        try:
            requested_wait = float(retry_after) if retry_after is not None else 0.25
        except ValueError:
            requested_wait = 0.25
        if not math.isfinite(requested_wait) or requested_wait < 0:
            requested_wait = 0.25
        await self._sleep(min(requested_wait, maximum_wait))
        return True

    @staticmethod
    def _status_code(status: int) -> ErrorCode:
        if status in {401, 403}:
            return ErrorCode.AUTH_FAILED
        if status == 402:
            return ErrorCode.QUOTA_EXHAUSTED
        if status == 429:
            return ErrorCode.RATE_LIMITED
        return ErrorCode.PROVIDER_ERROR
