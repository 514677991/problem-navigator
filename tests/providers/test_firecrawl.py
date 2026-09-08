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
    MapRequest,
    Route,
    SearchRequest,
)
from web_research.providers.base import ProviderTransport
from web_research.providers.firecrawl import FirecrawlProvider


REQUEST_ID = "firecrawl-request-01"
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
FIXTURES = json.loads(
    (Path(__file__).parents[1] / "fixtures/providers/firecrawl.json").read_text("utf-8")
)


def provider(handler: httpx.MockTransport) -> tuple[FirecrawlProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    return FirecrawlProvider("firecrawl-test-key", ProviderTransport(client), clock=lambda: NOW), client


@pytest.mark.asyncio
async def test_papers_uses_frozen_get_wire_contract_and_maps_every_supported_primary_id() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURES["papers_success"])

    firecrawl, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await firecrawl.search(
            "papers",
            SearchRequest(query="safety research", direction=Direction.ACADEMIC, route=Route.PRIMARY),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert len(requests) == 1
    sent = requests[0]
    assert sent.method == "GET"
    assert str(sent.url) == "https://api.firecrawl.dev/v2/search/research/papers?query=safety+research&k=10"
    assert sent.headers["Authorization"] == "Bearer firecrawl-test-key"
    assert result.model_dump(mode="json") == {
        "request_id": REQUEST_ID,
        "status": "SUCCESS",
        "retrieved_at": "2026-09-05T00:00:00Z",
        "truncated": False,
        "provider": "firecrawl",
        "direction": "academic",
        "route_used": "primary",
        "sources": [
            {"url": "https://arxiv.org/abs/2401.00001", "title": "Arxiv paper", "snippet": "Preprint summary", "published_at": None, "source_type": "publication"},
            {"url": "https://pubmed.ncbi.nlm.nih.gov/12345/", "title": "PubMed paper", "snippet": "Medical summary", "published_at": None, "source_type": "publication"},
            {"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/", "title": "PMC paper", "snippet": "Archive summary", "published_at": None, "source_type": "publication"},
            {"url": "https://doi.org/10.1000/a%20path/part", "title": "DOI paper", "snippet": "DOI summary", "published_at": None, "source_type": "publication"},
            {"url": "https://papers.example.org/record", "title": "Web paper", "snippet": "Web summary", "published_at": None, "source_type": "publication"},
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "search_request",
    [
        SearchRequest(query="q", freshness=Freshness.DAY),
        SearchRequest(query="q", domains=["example.com"]),
    ],
)
async def test_papers_rejects_unsupported_filters_without_http(search_request: SearchRequest) -> None:
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=FIXTURES["papers_success"])

    firecrawl, client = provider(httpx.MockTransport(handler))
    async with client:
        with pytest.raises(CoreError) as caught:
            await firecrawl.search("papers", search_request, REQUEST_ID, time.monotonic() + 10)

    assert caught.value.code is ErrorCode.INVALID_REQUEST
    assert calls == 0


@pytest.mark.asyncio
async def test_developer_uses_frozen_post_wire_contract_and_supported_filters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURES["developer_success"])

    firecrawl, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await firecrawl.search(
            "developer",
            SearchRequest(
                query="client authentication",
                direction=Direction.DEVELOPER,
                route=Route.PRIMARY,
                freshness=Freshness.MONTH,
                domains=["docs.example.com"],
            ),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert len(requests) == 1
    sent = requests[0]
    assert sent.method == "POST"
    assert str(sent.url) == "https://api.firecrawl.dev/v2/search"
    assert sent.headers["Authorization"] == "Bearer firecrawl-test-key"
    assert sent.headers["content-type"] == "application/json"
    assert json.loads(sent.content) == {
        "query": "client authentication",
        "limit": 10,
        "categories": [{"type": "developer"}],
        "timeout": 45000,
        "includeDomains": ["docs.example.com"],
        "tbs": "qdr:m",
    }
    assert result.sources[0].model_dump(mode="json") == {
        "url": "https://docs.example.com/guide",
        "title": "Developer guide",
        "snippet": "API documentation",
        "published_at": None,
        "source_type": "developer",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        (
            "papers",
            {
                "success": True,
                "results": [
                    {
                        "primaryId": "arxiv:2401.00001",
                        "title": "Long abstract",
                        "abstract": "a" * 2_001,
                    }
                ],
            },
        ),
        (
            "developer",
            {
                "success": True,
                "data": {
                    "web": [
                        {
                            "url": "https://docs.example.com/long",
                            "title": "Long description",
                            "description": "d" * 2_001,
                        }
                    ]
                },
            },
        ),
    ],
)
async def test_search_reports_adapter_snippet_clipping(
    operation: str, payload: dict[str, object]
) -> None:
    firecrawl, client = provider(
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    async with client:
        result = await firecrawl.search(
            operation, SearchRequest(query="q"), REQUEST_ID, time.monotonic() + 10
        )

    assert result.sources[0].snippet in {"a" * 2_000, "d" * 2_000}
    assert result.truncated is True


@pytest.mark.asyncio
async def test_scrape_sends_all_fixed_safety_and_cache_fields_and_uses_validated_final_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURES["scrape_success"])

    firecrawl, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await firecrawl.fetch(
            FetchRequest(url="https://example.com/requested", route=Route.PRIMARY),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert len(requests) == 1
    sent = requests[0]
    assert sent.method == "POST"
    assert str(sent.url) == "https://api.firecrawl.dev/v2/scrape"
    assert sent.headers["Authorization"] == "Bearer firecrawl-test-key"
    assert json.loads(sent.content) == {
        "url": "https://example.com/requested",
        "formats": [{"type": "markdown"}],
        "onlyMainContent": True,
        "skipTlsVerification": False,
        "timeout": 45000,
        "maxAge": 0,
        "storeInCache": False,
    }
    assert result.model_dump(mode="json") == {
        "request_id": REQUEST_ID,
        "status": "SUCCESS",
        "retrieved_at": "2026-09-05T00:00:00Z",
        "truncated": False,
        "provider": "firecrawl",
        "route_used": "primary",
        "url": "https://example.com/final",
        "content": "# Retrieved page\n\nUseful content.",
    }


@pytest.mark.asyncio
async def test_scrape_rejects_nonempty_query_without_http() -> None:
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=FIXTURES["scrape_success"])

    firecrawl, client = provider(httpx.MockTransport(handler))
    async with client:
        with pytest.raises(CoreError) as caught:
            await firecrawl.fetch(
                FetchRequest(url="https://example.com/page", query="only this section"),
                REQUEST_ID,
                time.monotonic() + 10,
            )

    assert caught.value.code is ErrorCode.INVALID_REQUEST
    assert calls == 0


@pytest.mark.asyncio
async def test_map_uses_frozen_wire_contract_and_deduplicates_valid_urls_in_order() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FIXTURES["map_success"])

    firecrawl, client = provider(httpx.MockTransport(handler))
    async with client:
        result = await firecrawl.map(
            MapRequest(url="https://example.com", query="reference docs"),
            REQUEST_ID,
            time.monotonic() + 10,
        )

    assert len(requests) == 1
    sent = requests[0]
    assert sent.method == "POST"
    assert str(sent.url) == "https://api.firecrawl.dev/v2/map"
    assert sent.headers["Authorization"] == "Bearer firecrawl-test-key"
    assert json.loads(sent.content) == {
        "url": "https://example.com",
        "limit": 50,
        "timeout": 45000,
        "search": "reference docs",
    }
    assert result.urls == ["https://example.com/one", "https://example.com/two"]


@pytest.mark.asyncio
async def test_map_caps_valid_urls_at_fifty_and_sets_truncated() -> None:
    payload = {
        "success": True,
        "links": [{"url": f"https://example.com/{index}"} for index in range(51)],
    }
    firecrawl, client = provider(httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    async with client:
        result = await firecrawl.map(MapRequest(url="https://example.com"), REQUEST_ID, time.monotonic() + 10)

    assert result.urls == [f"https://example.com/{index}" for index in range(50)]
    assert result.truncated is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "operation", "input_request", "payload"),
    [
        ("search", "papers", SearchRequest(query="q"), {"success": False, "results": []}),
        ("search", "papers", SearchRequest(query="q"), FIXTURES["papers_schema_drift"]),
        ("search", "developer", SearchRequest(query="q"), FIXTURES["developer_schema_drift"]),
        ("search", "papers", SearchRequest(query="q"), {"success": True, "results": [{"title": "Unknown", "primaryId": "internal:123"}]}),
        ("fetch", "", FetchRequest(url="https://example.com/page"), {"success": False, "data": {}}),
        ("fetch", "", FetchRequest(url="https://example.com/page"), {"success": True}),
        ("fetch", "", FetchRequest(url="https://example.com/page"), {"success": True, "data": {"markdown": "x", "metadata": {"url": "http://127.0.0.1/private"}}}),
        ("map", "", MapRequest(url="https://example.com"), {"success": False, "links": []}),
        ("map", "", MapRequest(url="https://example.com"), {"success": True}),
        ("map", "", MapRequest(url="https://example.com"), {"success": True, "links": [{"url": "http://127.0.0.1/private"}]}),
    ],
)
async def test_non_success_schema_drift_or_only_invalid_result_urls_are_provider_errors(
    kind: str, operation: str, input_request: SearchRequest | FetchRequest | MapRequest, payload: dict[str, object]
) -> None:
    firecrawl, client = provider(httpx.MockTransport(lambda http_request: httpx.Response(200, json=payload)))
    async with client:
        with pytest.raises(CoreError) as caught:
            if kind == "search":
                assert isinstance(input_request, SearchRequest)
                await firecrawl.search(operation, input_request, REQUEST_ID, time.monotonic() + 10)
            elif kind == "fetch":
                assert isinstance(input_request, FetchRequest)
                await firecrawl.fetch(input_request, REQUEST_ID, time.monotonic() + 10)
            else:
                assert isinstance(input_request, MapRequest)
                await firecrawl.map(input_request, REQUEST_ID, time.monotonic() + 10)

    assert caught.value.code is ErrorCode.PROVIDER_ERROR
    assert "SECRET_PROVIDER_DETAIL" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "operation", "input_request", "payload"),
    [
        ("search", "papers", SearchRequest(query="q"), FIXTURES["papers_empty"]),
        ("search", "developer", SearchRequest(query="q"), FIXTURES["developer_empty"]),
        ("map", "", MapRequest(url="https://example.com"), {"success": True, "links": []}),
    ],
)
async def test_only_explicit_legal_empty_arrays_are_no_results(
    kind: str, operation: str, input_request: SearchRequest | MapRequest, payload: dict[str, object]
) -> None:
    firecrawl, client = provider(httpx.MockTransport(lambda http_request: httpx.Response(200, json=payload)))
    async with client:
        if kind == "search":
            assert isinstance(input_request, SearchRequest)
            result = await firecrawl.search(operation, input_request, REQUEST_ID, time.monotonic() + 10)
            assert result.sources == []
        else:
            assert isinstance(input_request, MapRequest)
            result = await firecrawl.map(input_request, REQUEST_ID, time.monotonic() + 10)
            assert result.urls == []

    assert result.status.value == "NO_RESULTS"
    assert result.truncated is False
