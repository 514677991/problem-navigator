from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from web_research.models import CoreError, Direction, ErrorCode, Freshness, Route, SearchRequest
from web_research.providers.base import ProviderTransport
from web_research.providers.brave import BraveProvider


REQUEST_ID = "brave-request-id-001"
FIXTURES = json.loads((Path(__file__).parents[1] / "fixtures/providers/brave.json").read_text("utf-8"))
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def provider(handler: httpx.MockTransport) -> tuple[BraveProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    return BraveProvider("brave-test-key", ProviderTransport(client), clock=lambda: NOW), client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "fixture_name", "expected_path", "expected_params", "expected_type"),
    [
        ("llm_context", "llm_context_success", "/res/v1/llm/context", {"q": "climate evidence", "count": "10", "maximum_number_of_urls": "10", "maximum_number_of_tokens": "8192", "freshness": "pw"}, "web"),
        ("news", "news_success", "/res/v1/news/search", {"q": "climate evidence", "count": "10", "freshness": "pw"}, "news"),
        ("web", "web_success", "/res/v1/web/search", {"q": "climate evidence", "count": "10", "freshness": "pw"}, "developer"),
    ],
)
async def test_brave_uses_frozen_wire_contract_and_normalizes_sources(
    operation: str, fixture_name: str, expected_path: str, expected_params: dict[str, str], expected_type: str
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURES[fixture_name])

    brave, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await brave.search(
            operation, SearchRequest(query="climate evidence", direction=Direction.AUTO, route=Route.PRIMARY, freshness=Freshness.WEEK), REQUEST_ID, time.monotonic() + 10
        )

    assert len(requests) == 1
    sent = requests[0]
    assert sent.method == "GET"
    assert sent.url.scheme == "https"
    assert sent.url.host == "api.search.brave.com"
    assert sent.url.path == expected_path
    assert dict(sent.url.params) == expected_params
    assert sent.headers["X-Subscription-Token"] == "brave-test-key"
    assert sent.headers["Accept"] == "application/json"
    assert sent.headers["Api-Version"] == "2026-02-06"
    assert result.request_id == REQUEST_ID
    assert result.status.value == "SUCCESS"
    assert result.sources[0].source_type.value == expected_type


@pytest.mark.asyncio
async def test_llm_context_joins_snippets_in_order_and_limits_to_two_thousand_characters() -> None:
    payload = {"grounding": {"generic": [{"url": "https://example.com/long", "title": "Long", "snippets": ["a" * 1500, "b" * 1500]}]}}
    brave, client = provider(httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    async with client:
        result = await brave.search("llm_context", SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10)

    assert result.sources[0].snippet == "a" * 1500 + "b" * 500
    assert result.truncated is True


@pytest.mark.asyncio
async def test_web_reports_description_clipping() -> None:
    payload = {
        "web": {
            "results": [
                {
                    "url": "https://example.com/long",
                    "title": "Long",
                    "description": "x" * 2_001,
                }
            ]
        }
    }
    brave, client = provider(
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    async with client:
        result = await brave.search(
            "web", SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10
        )

    assert result.sources[0].snippet == "x" * 2_000
    assert result.truncated is True


@pytest.mark.asyncio
@pytest.mark.parametrize("input_request", [SearchRequest(query="x" * 401), SearchRequest(query=" ".join(["x"] * 51)), SearchRequest(query="valid", domains=["example.com"])])
async def test_brave_rejects_unsupported_query_or_domains_without_http(input_request: SearchRequest) -> None:
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=FIXTURES["llm_context_success"])

    brave, client = provider(httpx.MockTransport(handler))
    async with client:
        with pytest.raises(CoreError) as caught:
            await brave.search("llm_context", input_request, REQUEST_ID, time.monotonic() + 10)

    assert caught.value.code is ErrorCode.INVALID_REQUEST
    assert calls == 0


@pytest.mark.asyncio
async def test_empty_array_is_no_results_but_schema_drift_or_only_invalid_urls_is_provider_error() -> None:
    cases = [
        ("llm_context", FIXTURES["empty"], ErrorCode.PROVIDER_ERROR),
        ("news", {"results": []}, None),
        ("llm_context", FIXTURES["schema_drift"], ErrorCode.PROVIDER_ERROR),
        ("web", {"web": {"results": [{"url": "http://127.0.0.1/private", "title": "Unsafe"}]}}, ErrorCode.PROVIDER_ERROR),
    ]
    for operation, payload, code in cases:
        brave, client = provider(httpx.MockTransport(lambda request, payload=payload: httpx.Response(200, json=payload)))
        async with client:
            if code is None:
                result = await brave.search(operation, SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10)
                assert result.status.value == "NO_RESULTS"
            else:
                with pytest.raises(CoreError) as caught:
                    await brave.search(operation, SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10)
                assert caught.value.code is code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        ("llm_context", {"grounding": {"generic": []}}),
        ("news", {"results": []}),
        ("web", {"web": {"results": []}}),
    ],
)
async def test_each_brave_operation_maps_a_legal_empty_array_to_no_results(
    operation: str, payload: dict[str, object]
) -> None:
    brave, client = provider(
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    async with client:
        result = await brave.search(
            operation, SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10
        )

    assert result.status.value == "NO_RESULTS"
    assert result.sources == []
