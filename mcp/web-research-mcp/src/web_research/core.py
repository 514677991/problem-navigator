"""Deterministic, transport-independent orchestration for public-web research."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from .config import ConfigSnapshot
from .models import (
    CoreError,
    Direction,
    ErrorCode,
    FetchRequest,
    FetchResult,
    MapRequest,
    MapResult,
    Provider,
    ResultStatus,
    Route,
    SearchRequest,
    SearchResult,
    SearchSource,
    validate_request_id,
)
from .security import UnsafeUrlError, normalize_public_url

if TYPE_CHECKING:
    from .providers import ProviderTransport


CALL_DEADLINE_SECONDS = 60.0

SEARCH_ROUTES: dict[tuple[Direction, Route], tuple[str, str]] = {
    (Direction.AUTO, Route.PRIMARY): ("brave", "llm_context"),
    (Direction.AUTO, Route.ALTERNATE): ("exa", "search_auto"),
    (Direction.NEWS, Route.PRIMARY): ("brave", "news"),
    (Direction.NEWS, Route.ALTERNATE): ("exa", "news"),
    (Direction.SEMANTIC, Route.PRIMARY): ("exa", "search_auto"),
    (Direction.ACADEMIC, Route.PRIMARY): ("firecrawl", "papers"),
    (Direction.ACADEMIC, Route.ALTERNATE): ("exa", "publication"),
    (Direction.DEVELOPER, Route.PRIMARY): ("firecrawl", "developer"),
    (Direction.DEVELOPER, Route.ALTERNATE): ("brave", "web"),
}
FETCH_ROUTES: dict[Route, tuple[str, str]] = {
    Route.PRIMARY: ("firecrawl", "scrape"),
    Route.ALTERNATE: ("exa", "contents"),
}
MAP_ROUTES: dict[Route, tuple[str, str]] = {Route.PRIMARY: ("firecrawl", "map")}


class ResearchCore:
    """Route one call to exactly one configured provider; never fallback."""

    def __init__(
        self,
        providers: Mapping[str, Any],
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._providers = dict(providers)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic
        self._request_id_factory = request_id_factory or (lambda: secrets.token_urlsafe(18))

    @classmethod
    def from_config(
        cls,
        snapshot: ConfigSnapshot,
        *,
        transport: ProviderTransport,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        request_id_factory: Callable[[], str] | None = None,
    ) -> "ResearchCore":
        """Construct exactly the adapters whose keys exist in a snapshot."""
        from .providers import configured_providers

        return cls(
            configured_providers(snapshot, transport, clock=clock),
            clock=clock,
            monotonic=monotonic,
            request_id_factory=request_id_factory,
        )

    async def search(
        self,
        query: str,
        direction: str = "auto",
        route: str = "primary",
        freshness: str = "",
        domains: list[str] | None = None,
        *,
        request_id: str | None = None,
    ) -> SearchResult:
        identifier = self._request_id(request_id)
        deadline = self._monotonic() + CALL_DEADLINE_SECONDS
        try:
            request = SearchRequest(
                query=query,
                direction=direction,
                route=route,
                freshness=freshness,
                domains=[] if domains is None else domains,
            )
        except (ValidationError, UnsafeUrlError, ValueError):
            raise self._error(identifier, ErrorCode.INVALID_REQUEST) from None

        selected = SEARCH_ROUTES.get((request.direction, request.route))
        if selected is None:
            raise self._error(identifier, ErrorCode.INVALID_REQUEST)
        provider_name, operation = selected
        if not self._search_route_supports_filters(request, provider_name, operation):
            raise self._error(identifier, ErrorCode.INVALID_REQUEST)
        provider = self._provider(identifier, provider_name)

        try:
            raw = await provider.search(operation, request, identifier, deadline)
            return self._normalize_search(raw, identifier, provider_name, request)
        except CoreError:
            raise
        except Exception:
            raise self._error(identifier, ErrorCode.PROVIDER_ERROR) from None

    async def fetch(
        self,
        url: str,
        query: str = "",
        route: str = "primary",
        *,
        request_id: str | None = None,
    ) -> FetchResult:
        identifier = self._request_id(request_id)
        deadline = self._monotonic() + CALL_DEADLINE_SECONDS
        try:
            request = FetchRequest(url=url, query=query, route=route)
        except (ValidationError, UnsafeUrlError, ValueError):
            raise self._error(identifier, ErrorCode.INVALID_REQUEST) from None

        selected = FETCH_ROUTES.get(request.route)
        if selected is None:
            raise self._error(identifier, ErrorCode.INVALID_REQUEST)
        provider_name, _operation = selected
        if provider_name == "firecrawl" and request.query:
            raise self._error(identifier, ErrorCode.INVALID_REQUEST)
        provider = self._provider(identifier, provider_name)

        try:
            raw = await provider.fetch(request, identifier, deadline)
            return self._normalize_fetch(raw, identifier, provider_name, request)
        except CoreError:
            raise
        except Exception:
            raise self._error(identifier, ErrorCode.PROVIDER_ERROR) from None

    async def map(
        self,
        url: str,
        query: str = "",
        *,
        request_id: str | None = None,
    ) -> MapResult:
        identifier = self._request_id(request_id)
        deadline = self._monotonic() + CALL_DEADLINE_SECONDS
        try:
            request = MapRequest(url=url, query=query)
        except (ValidationError, UnsafeUrlError, ValueError):
            raise self._error(identifier, ErrorCode.INVALID_REQUEST) from None

        provider_name, _operation = MAP_ROUTES[Route.PRIMARY]
        provider = self._provider(identifier, provider_name)
        try:
            raw = await provider.map(request, identifier, deadline)
            return self._normalize_map(raw, identifier)
        except CoreError:
            raise
        except Exception:
            raise self._error(identifier, ErrorCode.PROVIDER_ERROR) from None

    def _request_id(self, supplied: str | None) -> str:
        try:
            value = supplied if supplied is not None else self._request_id_factory()
            return validate_request_id(value)
        except (TypeError, ValueError):
            return secrets.token_urlsafe(18)

    def _provider(self, request_id: str, name: str) -> Any:
        provider = self._providers.get(name)
        if provider is None:
            raise self._error(request_id, ErrorCode.NOT_CONFIGURED)
        return provider

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _search_route_supports_filters(
        request: SearchRequest, provider_name: str, operation: str
    ) -> bool:
        if provider_name == "brave":
            if request.domains:
                return False
            if len(request.query) > 400 or len(request.query.split()) > 50:
                return False
        if provider_name == "firecrawl" and operation == "papers":
            return not request.domains and not request.freshness.value
        return True

    @staticmethod
    def _error(request_id: str, code: ErrorCode) -> CoreError:
        return CoreError(request_id, code)

    def _normalize_search(
        self,
        raw: Any,
        request_id: str,
        provider_name: str,
        request: SearchRequest,
    ) -> SearchResult:
        if not isinstance(raw, SearchResult):
            raw = SearchResult.model_validate(raw)
        sources, clipped = self._bounded_sources(raw.sources)
        return SearchResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if sources else ResultStatus.NO_RESULTS,
            provider=Provider(provider_name),
            direction=request.direction,
            route_used=request.route,
            retrieved_at=self._now(),
            truncated=bool(raw.truncated or clipped) if sources else False,
            sources=sources,
        )

    def _normalize_fetch(
        self,
        raw: Any,
        request_id: str,
        provider_name: str,
        request: FetchRequest,
    ) -> FetchResult:
        if not isinstance(raw, FetchResult):
            raw = FetchResult.model_validate(raw)
        if not isinstance(raw.content, str):
            raise TypeError("provider content is not text")
        content = raw.content[:20_000]
        return FetchResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if content else ResultStatus.NO_RESULTS,
            provider=Provider(provider_name),
            route_used=request.route,
            url=raw.url,
            content=content,
            retrieved_at=self._now(),
            truncated=bool(raw.truncated or len(raw.content) > 20_000) if content else False,
        )

    def _normalize_map(self, raw: Any, request_id: str) -> MapResult:
        if not isinstance(raw, MapResult):
            raw = MapResult.model_validate(raw)
        urls, clipped = self._bounded_urls(raw.urls)
        return MapResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if urls else ResultStatus.NO_RESULTS,
            provider=Provider.FIRECRAWL,
            route_used=Route.PRIMARY,
            url=raw.url,
            urls=urls,
            retrieved_at=self._now(),
            truncated=bool(raw.truncated or clipped) if urls else False,
        )

    @staticmethod
    def _bounded_sources(raw_sources: Any) -> tuple[list[SearchSource], bool]:
        if not isinstance(raw_sources, Sequence) or isinstance(raw_sources, (str, bytes)):
            raise TypeError("provider sources are not a sequence")
        truncated = len(raw_sources) > 10
        sources: list[SearchSource] = []
        for raw in raw_sources[:10]:
            if isinstance(raw, SearchSource):
                payload = raw.model_dump()
            elif isinstance(raw, Mapping):
                payload = dict(raw)
            else:
                raise TypeError("provider source is not an object")
            snippet = payload.get("snippet")
            if isinstance(snippet, str) and len(snippet) > 2_000:
                payload["snippet"] = snippet[:2_000]
                truncated = True
            sources.append(SearchSource.model_validate(payload))
        return sources, truncated

    @staticmethod
    def _bounded_urls(raw_urls: Any) -> tuple[list[str], bool]:
        if not isinstance(raw_urls, Sequence) or isinstance(raw_urls, (str, bytes)):
            raise TypeError("provider URLs are not a sequence")
        return [normalize_public_url(value) for value in raw_urls[:50]], len(raw_urls) > 50
