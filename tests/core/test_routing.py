from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from web_research.core import FETCH_ROUTES, MAP_ROUTES, SEARCH_ROUTES, ResearchCore
from web_research.models import (
    CoreError,
    Direction,
    ErrorCode,
    FetchResult,
    MapResult,
    Route,
    SearchResult,
    SearchSource,
)


class FakeProvider:
    def __init__(self, name: str, *, failure: Exception | None = None) -> None:
        self.name = name
        self.failure = failure
        self.calls: list[tuple[str, str]] = []

    async def search(
        self, operation: str, request: object, request_id: str, deadline: float
    ) -> SearchResult:
        self.calls.append(("search", operation))
        if self.failure:
            raise self.failure
        return SearchResult(
            request_id=request_id,
            status="SUCCESS",
            provider=self.name,
            direction=getattr(request, "direction"),
            route_used=getattr(request, "route"),
            retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            truncated=False,
            sources=[SearchSource(url="https://example.com/a", title=self.name, source_type="web")],
        )

    async def fetch(
        self, request: object, request_id: str, deadline: float
    ) -> FetchResult:
        self.calls.append(("fetch", "contents"))
        if self.failure:
            raise self.failure
        return FetchResult(
            request_id=request_id,
            status="SUCCESS",
            provider=self.name,
            route_used=getattr(request, "route"),
            url=getattr(request, "url"),
            content="content",
            retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            truncated=False,
        )

    async def map(
        self, request: object, request_id: str, deadline: float
    ) -> MapResult:
        self.calls.append(("map", "map"))
        if self.failure:
            raise self.failure
        return MapResult(
            request_id=request_id,
            status="SUCCESS",
            provider="firecrawl",
            route_used="primary",
            url=getattr(request, "url"),
            urls=["https://example.com/a"],
            retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            truncated=False,
        )


def _core(*providers: FakeProvider) -> ResearchCore:
    return ResearchCore(
        {provider.name: provider for provider in providers},
        clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
        request_id_factory=lambda: "a" * 16,
    )


def test_fixed_route_tables_do_not_offer_unsupported_fallbacks() -> None:
    assert SEARCH_ROUTES[(Direction.AUTO, Route.PRIMARY)] == ("brave", "llm_context")
    assert SEARCH_ROUTES[(Direction.ACADEMIC, Route.PRIMARY)] == ("firecrawl", "papers")
    assert (Direction.SEMANTIC, Route.ALTERNATE) not in SEARCH_ROUTES
    assert FETCH_ROUTES[Route.PRIMARY] == ("firecrawl", "scrape")
    assert MAP_ROUTES[Route.PRIMARY] == ("firecrawl", "map")


def test_semantic_alternate_and_map_alternate_fail_without_provider_call() -> None:
    provider = FakeProvider("exa")
    core = _core(provider)
    with pytest.raises(CoreError) as search_error:
        asyncio.run(core.search("query", direction="semantic", route="alternate"))
    assert search_error.value.code is ErrorCode.INVALID_REQUEST
    assert provider.calls == []

    assert Route.ALTERNATE not in MAP_ROUTES


def test_one_core_call_hits_exactly_one_selected_provider() -> None:
    brave, exa, firecrawl = FakeProvider("brave"), FakeProvider("exa"), FakeProvider("firecrawl")
    result = asyncio.run(_core(brave, exa, firecrawl).search("query", direction="auto", route="primary"))
    assert result.provider.value == "brave"
    assert brave.calls == [("search", "llm_context")]
    assert exa.calls == []
    assert firecrawl.calls == []


def test_provider_failure_is_not_rerouted_and_message_does_not_leak_request_data() -> None:
    secret = "query=confidential&token=abc"
    brave, exa = FakeProvider("brave", failure=RuntimeError(secret)), FakeProvider("exa")
    with pytest.raises(CoreError) as raised:
        asyncio.run(_core(brave, exa).search(secret, direction="auto", route="primary"))
    assert raised.value.code is ErrorCode.PROVIDER_ERROR
    assert secret not in raised.value.message
    assert "token" not in raised.value.message.lower()
    assert brave.calls == [("search", "llm_context")]
    assert exa.calls == []


@pytest.mark.parametrize(
    "provider_name, call",
    [
        ("firecrawl", lambda core: core.search("query", direction="academic", freshness="week")),
        ("firecrawl", lambda core: core.search("query", direction="academic", domains=["example.com"])),
        ("brave", lambda core: core.search("query", direction="auto", domains=["example.com"])),
        ("brave", lambda core: core.search("query", direction="news", domains=["example.com"])),
        ("brave", lambda core: core.search("query", direction="developer", route="alternate", domains=["example.com"])),
        ("firecrawl", lambda core: core.fetch("https://example.com", query="nonempty")),
    ],
)
def test_incompatible_route_filters_fail_before_provider_call(provider_name: str, call: object) -> None:
    provider = FakeProvider(provider_name)
    with pytest.raises(CoreError) as raised:
        asyncio.run(call(_core(provider)))
    assert raised.value.code is ErrorCode.INVALID_REQUEST
    assert provider.calls == []


def test_compatible_route_filters_dispatch_once_to_selected_provider() -> None:
    exa, firecrawl = FakeProvider("exa"), FakeProvider("firecrawl")
    core = _core(exa, firecrawl)
    asyncio.run(core.search("query", direction="academic", route="alternate", freshness="week", domains=["example.com"]))
    asyncio.run(core.search("query", direction="developer", freshness="week", domains=["example.com"]))
    asyncio.run(core.fetch("https://example.com", query="excerpt", route="alternate"))
    asyncio.run(core.map("https://example.com", query="site overview"))
    assert exa.calls == [("search", "publication"), ("fetch", "contents")]
    assert firecrawl.calls == [("search", "developer"), ("map", "map")]


def test_not_configured_error_has_safe_exact_serialization() -> None:
    with pytest.raises(CoreError) as raised:
        asyncio.run(_core().search("query", request_id="a" * 16))
    assert raised.value.as_dict() == {
        "request_id": "a" * 16,
        "code": "NOT_CONFIGURED",
        "message": "Selected route is not configured.",
    }


def test_core_error_constructor_uses_fixed_message_and_rejects_arbitrary_message() -> None:
    error = CoreError("a" * 16, ErrorCode.PROVIDER_ERROR)
    assert error.as_dict()["message"] == "Selected route provider failed."
    with pytest.raises(TypeError):
        CoreError("a" * 16, ErrorCode.PROVIDER_ERROR, "token=secret")


def test_core_error_message_is_read_only_and_always_derived_from_its_code() -> None:
    error = CoreError("a" * 16, ErrorCode.PROVIDER_ERROR)
    safe_message = "Selected route provider failed."
    with pytest.raises(AttributeError):
        error.message = "token=secret"
    error.__dict__["message"] = "token=secret"
    assert error.message == safe_message
    assert error.as_dict()["message"] == safe_message
    assert str(error) == safe_message
    assert error.args == (safe_message,)


def test_core_truncates_provider_output_to_documented_limits() -> None:
    class ExcessProvider(FakeProvider):
        async def search(
            self, operation: str, request: object, request_id: str, deadline: float
        ) -> SearchResult:
            self.calls.append(("search", operation))
            sources = [
                SearchSource(url=f"https://example{i}.com", title=str(i), source_type="web")
                for i in range(11)
            ]
            return SearchResult.model_construct(
                request_id=request_id,
                status="SUCCESS",
                provider="brave",
                direction=getattr(request, "direction"),
                route_used=getattr(request, "route"),
                retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                truncated=False,
                sources=sources,
            )

    result = asyncio.run(_core(ExcessProvider("brave")).search("query"))
    assert len(result.sources) == 10
    assert result.truncated is True


def test_importing_core_does_not_import_fastmcp() -> None:
    project_root = Path(__file__).resolve().parents[2] / "mcp" / "web-research-mcp"
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; import web_research.core; assert 'fastmcp' not in sys.modules"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
