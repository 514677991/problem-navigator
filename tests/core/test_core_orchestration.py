from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

from web_research.config import ConfigSnapshot
from web_research.core import ResearchCore
from web_research.models import (
    CoreError,
    ErrorCode,
    FetchResult,
    MapResult,
    SearchResult,
    SearchSource,
    SourceType,
)
from web_research.providers import ProviderTransport


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
REQUEST_ID = "core-request-id-01"


class RecordingProvider:
    def __init__(self, name: str, *, failure: CoreError | None = None) -> None:
        self.name = name
        self.failure = failure
        self.calls: list[tuple[str, str, object, str, float]] = []

    async def search(
        self, operation: str, request: object, request_id: str, deadline: float
    ) -> SearchResult:
        self.calls.append(("search", operation, request, request_id, deadline))
        if self.failure is not None:
            raise self.failure
        return SearchResult(
            request_id=request_id,
            status="SUCCESS",
            provider=self.name,
            direction=getattr(request, "direction"),
            route_used=getattr(request, "route"),
            retrieved_at=NOW,
            truncated=False,
            sources=[
                SearchSource(
                    url="https://example.com/source",
                    title=self.name,
                    source_type=SourceType.WEB,
                )
            ],
        )

    async def fetch(
        self, request: object, request_id: str, deadline: float
    ) -> FetchResult:
        self.calls.append(("fetch", "contents", request, request_id, deadline))
        return FetchResult(
            request_id=request_id,
            status="SUCCESS",
            provider=self.name,
            route_used=getattr(request, "route"),
            url=getattr(request, "url"),
            content="content",
            retrieved_at=NOW,
            truncated=False,
        )

    async def map(
        self, request: object, request_id: str, deadline: float
    ) -> MapResult:
        self.calls.append(("map", "map", request, request_id, deadline))
        return MapResult(
            request_id=request_id,
            status="SUCCESS",
            provider="firecrawl",
            route_used="primary",
            url=getattr(request, "url"),
            urls=["https://example.com/source"],
            retrieved_at=NOW,
            truncated=False,
        )


def _core(*providers: RecordingProvider, monotonic: Any = lambda: 100.0) -> ResearchCore:
    return ResearchCore(
        {provider.name: provider for provider in providers},
        clock=lambda: NOW,
        monotonic=monotonic,
        request_id_factory=lambda: REQUEST_ID,
    )


def test_config_snapshot_builds_only_configured_provider_adapters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "grounding": {
                    "generic": [
                        {
                            "url": "https://example.com/source",
                            "title": "Configured Brave",
                            "snippets": ["evidence"],
                        }
                    ]
                }
            },
        )

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            core = ResearchCore.from_config(
                ConfigSnapshot(brave_api_key="brave-key"),
                transport=ProviderTransport(client, monotonic=lambda: 100.0),
                clock=lambda: NOW,
                monotonic=lambda: 100.0,
                request_id_factory=lambda: REQUEST_ID,
            )
            result = await core.search("query")
            assert result.provider.value == "brave"
            with pytest.raises(CoreError) as raised:
                await core.search("query", direction="semantic")
            assert raised.value.code is ErrorCode.NOT_CONFIGURED

    asyncio.run(exercise())
    assert len(requests) == 1


def test_from_config_requires_caller_owned_transport() -> None:
    with pytest.raises(TypeError):
        ResearchCore.from_config(ConfigSnapshot())


def test_core_passes_one_absolute_sixty_second_deadline_and_generated_request_id() -> None:
    brave = RecordingProvider("brave")

    result = asyncio.run(_core(brave).search("query"))

    assert result.request_id == REQUEST_ID
    assert len(brave.calls) == 1
    _, operation, request, request_id, deadline = brave.calls[0]
    assert operation == "llm_context"
    assert getattr(request, "query") == "query"
    assert request_id == REQUEST_ID
    assert deadline == 160.0


def test_core_reapplies_all_output_bounds_and_truncated_flags() -> None:
    class ExcessProvider(RecordingProvider):
        async def search(
            self, operation: str, request: object, request_id: str, deadline: float
        ) -> SearchResult:
            self.calls.append(("search", operation, request, request_id, deadline))
            sources = [
                SearchSource.model_construct(
                    url=f"https://example{i}.com/source",
                    title=str(i),
                    snippet=("x" * 2001 if i == 0 else None),
                    published_at=None,
                    source_type=SourceType.WEB,
                )
                for i in range(11)
            ]
            return SearchResult.model_construct(
                request_id="upstream-id-must-not-win",
                status="SUCCESS",
                provider="brave",
                direction="auto",
                route_used="primary",
                retrieved_at=NOW,
                truncated=False,
                sources=sources,
            )

        async def fetch(
            self, request: object, request_id: str, deadline: float
        ) -> FetchResult:
            return FetchResult.model_construct(
                request_id="upstream-id-must-not-win",
                status="SUCCESS",
                provider="exa",
                route_used="alternate",
                url=getattr(request, "url"),
                content="x" * 20_001,
                retrieved_at=NOW,
                truncated=False,
            )

        async def map(
            self, request: object, request_id: str, deadline: float
        ) -> MapResult:
            return MapResult.model_construct(
                request_id="upstream-id-must-not-win",
                status="SUCCESS",
                provider="firecrawl",
                route_used="primary",
                url=getattr(request, "url"),
                urls=[f"https://example{i}.com/page" for i in range(51)],
                retrieved_at=NOW,
                truncated=False,
            )

    brave = ExcessProvider("brave")
    exa = ExcessProvider("exa")
    firecrawl = ExcessProvider("firecrawl")
    core = _core(brave, exa, firecrawl)

    search = asyncio.run(core.search("query"))
    fetch = asyncio.run(core.fetch("https://example.com", route="alternate"))
    mapped = asyncio.run(core.map("https://example.com"))

    assert search.request_id == fetch.request_id == mapped.request_id == REQUEST_ID
    assert len(search.sources) == 10
    assert len(search.sources[0].snippet or "") == 2000
    assert search.truncated is True
    assert len(fetch.content) == 20_000
    assert fetch.truncated is True
    assert len(mapped.urls) == 50
    assert mapped.truncated is True


def test_core_prechecks_route_capability_without_calling_any_adapter() -> None:
    firecrawl = RecordingProvider("firecrawl")
    brave = RecordingProvider("brave")
    core = _core(firecrawl, brave)

    with pytest.raises(CoreError) as semantic:
        asyncio.run(core.search("query", direction="semantic", route="alternate"))
    with pytest.raises(CoreError) as academic:
        asyncio.run(core.search("query", direction="academic", freshness="day"))
    with pytest.raises(CoreError) as domains:
        asyncio.run(core.search("query", domains=["example.com"]))
    with pytest.raises(CoreError) as too_many_characters:
        asyncio.run(core.search("x" * 401))
    with pytest.raises(CoreError) as too_many_words:
        asyncio.run(core.search(" ".join(["word"] * 51)))

    assert semantic.value.code is ErrorCode.INVALID_REQUEST
    assert academic.value.code is ErrorCode.INVALID_REQUEST
    assert domains.value.code is ErrorCode.INVALID_REQUEST
    assert too_many_characters.value.code is ErrorCode.INVALID_REQUEST
    assert too_many_words.value.code is ErrorCode.INVALID_REQUEST
    assert firecrawl.calls == []
    assert brave.calls == []


def test_core_propagates_core_error_without_fallback() -> None:
    failure = CoreError(REQUEST_ID, ErrorCode.AUTH_FAILED)
    brave = RecordingProvider("brave", failure=failure)
    exa = RecordingProvider("exa")

    with pytest.raises(CoreError) as raised:
        asyncio.run(_core(brave, exa).search("query"))

    assert raised.value is failure
    assert len(brave.calls) == 1
    assert exa.calls == []
