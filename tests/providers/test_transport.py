from __future__ import annotations

import json

import httpx
import pytest

from web_research.models import CoreError, ErrorCode
from web_research.providers.base import MAX_RESPONSE_BYTES, ProviderTransport


REQUEST_ID = "transport-request-0001"


class VirtualTime:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class DeadlineCrossingStream(httpx.AsyncByteStream):
    def __init__(self, timer: VirtualTime) -> None:
        self._timer = timer

    async def __aiter__(self):
        self._timer.now += 1.0
        yield b'{"ok": true}'

    async def aclose(self) -> None:
        return None


def response(status: int, *, headers: dict[str, str] | None = None, body: object = None) -> httpx.Response:
    return httpx.Response(status, headers=headers, content=json.dumps(body or {}).encode())


@pytest.mark.asyncio
async def test_retry_after_numeric_seconds_is_capped_before_deadline() -> None:
    timer = VirtualTime()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(429, headers={"Retry-After": "10"}) if calls == 1 else response(200, body={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        value = await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
            "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=102.0
        )

    assert value == {"ok": True}
    assert calls == 2
    assert timer.sleeps == [1.0]


@pytest.mark.asyncio
async def test_retry_after_non_numeric_uses_quarter_second() -> None:
    timer = VirtualTime()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(503, headers={"Retry-After": "tomorrow"}) if calls == 1 else response(200, body={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        value = await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
            "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=102.0
        )

    assert value == {"ok": True}
    assert calls == 2
    assert timer.sleeps == [0.25]


@pytest.mark.asyncio
async def test_retry_is_skipped_when_deadline_cannot_leave_one_second() -> None:
    timer = VirtualTime()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CoreError) as caught:
            await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
                "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=100.9
            )

    assert caught.value.code is ErrorCode.PROVIDER_ERROR
    assert calls == 1
    assert timer.sleeps == []


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [httpx.ReadTimeout("timed out"), httpx.ReadError("reset")])
async def test_read_timeout_and_reset_are_not_retried(error: httpx.HTTPError) -> None:
    timer = VirtualTime()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise error

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CoreError) as caught:
            await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
                "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=110.0
            )

    assert caught.value.code is ErrorCode.NETWORK_ERROR
    assert calls == 1


@pytest.mark.asyncio
async def test_connect_error_is_retried_exactly_once() -> None:
    timer = VirtualTime()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection failed", request=request)
        return response(200, body={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        value = await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
            "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=110.0
        )

    assert value == {"ok": True}
    assert calls == 2
    assert timer.sleeps == [0.25]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [(401, ErrorCode.AUTH_FAILED), (402, ErrorCode.QUOTA_EXHAUSTED), (429, ErrorCode.RATE_LIMITED), (500, ErrorCode.PROVIDER_ERROR)],
)
async def test_http_errors_are_mapped_without_provider_body_or_key(status: int, code: ErrorCode) -> None:
    timer = VirtualTime()
    secret_body = {"error": "provider detail: SECRET_BODY", "key": "SECRET_KEY"}

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response(status, body=secret_body))) as client:
        with pytest.raises(CoreError) as caught:
            await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
                "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={"Authorization": "SECRET_KEY"}, deadline=110.0
            )

    assert caught.value.code is code
    assert "SECRET_BODY" not in str(caught.value)
    assert "SECRET_KEY" not in str(caught.value)


@pytest.mark.asyncio
async def test_response_larger_than_five_mebibytes_is_rejected_before_json_parsing() -> None:
    oversized = b"x" * (5 * 1024 * 1024 + 1)
    timer = VirtualTime()

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=oversized))) as client:
        with pytest.raises(CoreError) as caught:
            await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
                "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=110.0
            )

    assert caught.value.code is ErrorCode.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_response_exactly_five_mebibytes_is_parsed() -> None:
    encoded = b'{"data":"' + b"x" * (MAX_RESPONSE_BYTES - len(b'{"data":""}')) + b'"}'
    assert len(encoded) == MAX_RESPONSE_BYTES
    timer = VirtualTime()

    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=encoded))) as client:
        value = await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
            "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=110.0
        )

    assert value["data"] == "x" * (MAX_RESPONSE_BYTES - len(b'{"data":""}'))


@pytest.mark.asyncio
async def test_stream_crossing_monotonic_deadline_is_network_error_not_success() -> None:
    timer = VirtualTime()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=DeadlineCrossingStream(timer))
        )
    ) as client:
        with pytest.raises(CoreError) as caught:
            await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
                "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=100.5
            )

    assert caught.value.code is ErrorCode.NETWORK_ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_after", ["NaN", "inf", "-inf", "-1"])
async def test_non_finite_or_negative_retry_after_uses_quarter_second(retry_after: str) -> None:
    timer = VirtualTime()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(503, headers={"Retry-After": retry_after}) if calls == 1 else response(200, body={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        value = await ProviderTransport(client, monotonic=timer.monotonic, sleep=timer.sleep).request_json(
            "GET", "https://provider.example/search", request_id=REQUEST_ID, headers={}, deadline=110.0
        )

    assert value == {"ok": True}
    assert calls == 2
    assert timer.sleeps == [0.25]
