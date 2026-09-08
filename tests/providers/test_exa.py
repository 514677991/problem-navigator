from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from web_research.models import (
    CoreError,
    Direction,
    ErrorCode,
    FetchRequest,
    Freshness,
    Route,
    SearchRequest,
)
from web_research.providers.base import ProviderTransport
from web_research.providers.exa import ExaProvider


REQUEST_ID = "exa-request-id-00001"
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
FIXTURES = json.loads(
    (Path(__file__).parents[1] / "fixtures/providers/exa.json").read_text("utf-8")
)


def provider(handler: httpx.MockTransport) -> tuple[ExaProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    return ExaProvider("exa-test-key", ProviderTransport(client), clock=lambda: NOW), client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "expected_body", "expected_source_type"),
    [
        ("search_auto", {"query": "climate evidence", "type": "auto", "numResults": 10, "contents": {"highlights": {"maxCharacters": 2000}}}, "web"),
        ("news", {"query": "climate evidence", "type": "auto", "category": "news", "numResults": 10, "contents": {"highlights": {"maxCharacters": 2000}}}, "news"),
        ("publication", {"query": "climate evidence", "type": "auto", "category": "publication", "numResults": 10, "contents": {"highlights": {"maxCharacters": 2000}}}, "publication"),
    ],
)
async def test_search_uses_frozen_operation_wire_contract_and_normalizes_sources(
    operation: str, expected_body: dict[str, object], expected_source_type: str
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURES["search_success"])

    exa, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await exa.search(
            operation,
            SearchRequest(query="climate evidence", direction=Direction.AUTO, route=Route.ALTERNATE),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert len(requests) == 1
    sent = requests[0]
    assert sent.method == "POST"
    assert str(sent.url) == "https://api.exa.ai/search"
    assert sent.headers["x-api-key"] == "exa-test-key"
    assert sent.headers["content-type"] == "application/json"
    assert json.loads(sent.content) == expected_body
    assert result.model_dump(mode="json") == {
        "request_id": REQUEST_ID,
        "status": "SUCCESS",
        "retrieved_at": "2026-09-05T00:00:00Z",
        "truncated": False,
        "provider": "exa",
        "direction": "auto",
        "route_used": "alternate",
        "sources": [
            {
                "url": "https://example.com/report",
                "title": "Evidence report",
                "snippet": "A concise evidence excerpt.\n\nA second excerpt.",
                "published_at": "2026-09-01T12:00:00Z",
                    "source_type": expected_source_type,
            }
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("freshness", "start"),
    [
        (Freshness.DAY, "2026-09-04T00:00:00Z"),
        (Freshness.WEEK, "2026-08-29T00:00:00Z"),
        (Freshness.MONTH, "2026-08-05T00:00:00Z"),
        (Freshness.YEAR, "2025-09-05T00:00:00Z"),
    ],
)
async def test_search_preserves_domains_and_computes_freshness_from_frozen_utc_clock(
    freshness: Freshness, start: str
) -> None:
    sent_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_bodies.append(json.loads(request.content))
        return httpx.Response(200, json=FIXTURES["search_empty"])

    exa, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await exa.search(
            "search_auto",
            SearchRequest(query="recent climate", freshness=freshness, domains=["example.com", "news.example.org"]),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert result.status.value == "NO_RESULTS"
    assert sent_bodies == [
        {
            "query": "recent climate",
            "type": "auto",
            "numResults": 10,
            "contents": {"highlights": {"maxCharacters": 2000}},
            "includeDomains": ["example.com", "news.example.org"],
            "startPublishedDate": start,
        }
    ]


@pytest.mark.asyncio
async def test_search_caps_at_ten_and_rejects_schema_drift_or_only_invalid_urls() -> None:
    valid = [
        {"url": f"https://example.com/{index}", "title": str(index), "text": "text"}
        for index in range(11)
    ]
    cases = [
        ({"results": valid}, None),
        (FIXTURES["schema_drift"], ErrorCode.PROVIDER_ERROR),
        ({"results": [{"url": "http://127.0.0.1/private", "title": "unsafe", "text": "x"}]}, ErrorCode.PROVIDER_ERROR),
        ({"results": [{"url": "https://example.com/page", "title": "bad highlights", "highlights": "not-an-array", "text": "must not hide schema drift"}]}, ErrorCode.PROVIDER_ERROR),
    ]
    for payload, code in cases:
        exa, client = provider(
            httpx.MockTransport(lambda request, payload=payload: httpx.Response(200, json=payload))
        )
        async with client:
            if code is None:
                result = await exa.search("search_auto", SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10)
                assert len(result.sources) == 10
                assert result.truncated is True
            else:
                with pytest.raises(CoreError) as caught:
                    await exa.search("search_auto", SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10)
                assert caught.value.code is code


@pytest.mark.asyncio
async def test_search_reports_clipped_highlights_and_uses_text_only_when_highlights_are_absent() -> None:
    cases = [
        (
            {"results": [{"url": "https://example.com/highlights", "title": "Highlights", "highlights": ["a" * 1_500, "b" * 1_500], "text": "ignored"}]},
            "a" * 1_500 + "\n\n" + "b" * 498,
            True,
        ),
        (
            {"results": [{"url": "https://example.com/text", "title": "Text fallback", "text": "legitimate provider text"}]},
            "legitimate provider text",
            False,
        ),
    ]
    for payload, expected_snippet, expected_truncated in cases:
        exa, client = provider(
            httpx.MockTransport(lambda request, payload=payload: httpx.Response(200, json=payload))
        )
        async with client:
            result = await exa.search(
                "search_auto", SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10
            )

        assert result.sources[0].snippet == expected_snippet
        assert result.truncated is expected_truncated


@pytest.mark.asyncio
async def test_search_rejects_an_operation_outside_the_frozen_wire_contract_without_http() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=FIXTURES["search_success"])

    exa, client = provider(httpx.MockTransport(handler))
    async with client:
        with pytest.raises(CoreError) as caught:
            await exa.search("developer", SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10)

    assert caught.value.code is ErrorCode.INVALID_REQUEST
    assert calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "fixture_name", "expected_body", "expected_content"),
    [
        ("", "contents_text_success", {"urls": ["https://example.com/page"], "text": {"maxCharacters": 10000}}, "Full page text."),
        ("what matters", "contents_highlights_success", {"urls": ["https://example.com/page"], "highlights": {"query": "what matters", "maxCharacters": 10000}}, "First matching passage.\n\nSecond matching passage."),
    ],
)
async def test_fetch_uses_one_paid_content_mode_and_returns_only_matched_content(
    query: str, fixture_name: str, expected_body: dict[str, object], expected_content: str
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURES[fixture_name])

    exa, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await exa.fetch(FetchRequest(url="https://example.com/page", query=query, route=Route.ALTERNATE), REQUEST_ID, time.monotonic() + 10)

    assert len(requests) == 1
    sent = requests[0]
    assert sent.method == "POST"
    assert str(sent.url) == "https://api.exa.ai/contents"
    assert sent.headers["x-api-key"] == "exa-test-key"
    assert sent.headers["content-type"] == "application/json"
    assert json.loads(sent.content) == expected_body
    assert result.model_dump(mode="json") == {
        "request_id": REQUEST_ID,
        "status": "SUCCESS",
        "retrieved_at": "2026-09-05T00:00:00Z",
        "truncated": bool(query),
        "provider": "exa",
        "route_used": "alternate",
        "url": "https://example.com/page",
        "content": expected_content,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "matching passage"])
async def test_fetch_clean_empty_content_is_no_results(query: str) -> None:
    exa, client = provider(httpx.MockTransport(lambda request: httpx.Response(200, json=FIXTURES["contents_empty_success"])))
    async with client:
        result = await exa.fetch(FetchRequest(url="https://example.com/page", query=query, route=Route.ALTERNATE), REQUEST_ID, time.monotonic() + 10)

    assert result.status.value == "NO_RESULTS"
    assert result.content == ""


@pytest.mark.asyncio
async def test_fetch_keeps_the_defensive_public_result_character_boundary() -> None:
    payload = {
        "results": [{"url": "https://example.com/page", "text": "x" * 20_001}],
        "statuses": [{"url": "https://example.com/page", "status": "success"}],
    }
    exa, client = provider(httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    async with client:
        result = await exa.fetch(FetchRequest(url="https://example.com/page", route=Route.ALTERNATE), REQUEST_ID, time.monotonic() + 10)

    assert result.content == "x" * 20_000
    assert result.truncated is True


@pytest.mark.asyncio
async def test_fetch_conservatively_reports_the_exact_provider_character_limit() -> None:
    payload = {
        "results": [{"url": "https://example.com/page", "text": "x" * 10_000}],
        "statuses": [{"url": "https://example.com/page", "status": "success"}],
    }
    exa, client = provider(
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    async with client:
        result = await exa.fetch(
            FetchRequest(url="https://example.com/page", route=Route.ALTERNATE),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert result.content == "x" * 10_000
    assert result.truncated is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested_url", "response_url", "canonical_url"),
    [
        (
            "https://BÜCHER.example:443/page?q=one#input-fragment",
            "https://xn--bcher-kva.example/page?q=one#output-fragment",
            "https://xn--bcher-kva.example/page?q=one",
        ),
        (
            "http://example.com/page?q=two#input-fragment",
            "http://example.com:80/page?q=two#output-fragment",
            "http://example.com/page?q=two",
        ),
    ],
)
async def test_fetch_matches_canonical_default_port_idna_and_fragment_equivalents(
    requested_url: str, response_url: str, canonical_url: str
) -> None:
    requests: list[httpx.Request] = []
    payload = {
        "results": [{"url": response_url, "text": "Canonical page text."}],
        "statuses": [{"url": response_url, "status": "success"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    exa, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await exa.fetch(
            FetchRequest(url=requested_url, route=Route.ALTERNATE),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert json.loads(requests[0].content) == {
        "urls": [canonical_url],
        "text": {"maxCharacters": 10000},
    }
    assert result.status.value == "SUCCESS"
    assert result.url == canonical_url
    assert result.content == "Canonical page text."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        FIXTURES["contents_status_error"],
        FIXTURES["schema_drift"],
        {"results": [{"url": "https://example.com/page", "text": "x"}], "statuses": []},
        {"results": [{"url": "https://example.com/page", "text": "x"}], "statuses": [{"url": "https://example.com/page", "status": "success"}, {"url": "https://example.com/other"}]},
        {"results": [{"url": "https://example.com/page", "text": "x"}], "statuses": [{"url": "https://example.com/page", "status": "success"}, {"url": "https://example.com/other", "status": "success"}]},
        {"results": [{"url": "https://example.com/page", "text": "x"}, {"url": "https://example.com/other", "text": "y"}], "statuses": [{"url": "https://example.com/page", "status": "success"}]},
        {"results": [{"url": "https://example.com/page", "text": "x"}, {"url": "https://example.com/other", "text": "y"}], "statuses": [{"url": "https://example.com/page", "status": "success"}, {"url": "https://example.com/other", "status": "success"}]},
        {"results": [{"url": "https://example.com/page", "text": "x"}], "statuses": [{"url": "https://example.com/page", "status": "success"}, {"url": "https://example.com/page", "status": "success"}]},
        {"results": [{"url": "https://example.com/other", "text": "x"}], "statuses": [{"url": "https://example.com/page", "status": "success"}]},
        {"results": [{"url": "https://example.com/page", "text": "x"}], "statuses": [{"url": "https://example.com/other", "status": "success"}]},
    ],
)
async def test_fetch_rejects_status_or_result_schema_drift(payload: dict[str, object]) -> None:
    exa, client = provider(httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    async with client:
        with pytest.raises(CoreError) as caught:
            await exa.fetch(FetchRequest(url="https://example.com/page", route=Route.ALTERNATE), REQUEST_ID, time.monotonic() + 10)

    assert caught.value.code is ErrorCode.PROVIDER_ERROR
    assert "SECRET_PROVIDER_DETAIL" not in str(caught.value)
