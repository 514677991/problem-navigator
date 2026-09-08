"""Fixed-contract Firecrawl Papers, Developer Search, Scrape, and Map adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError

from ..models import (
    CoreError,
    ErrorCode,
    FetchRequest,
    FetchResult,
    Freshness,
    MapRequest,
    MapResult,
    Provider,
    ResultStatus,
    Route,
    SearchRequest,
    SearchResult,
    SearchSource,
    SourceType,
)
from ..security import UnsafeUrlError, normalize_public_url
from .base import ProviderTransport


_FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v2"
_PAPERS_ENDPOINT = f"{_FIRECRAWL_BASE_URL}/search/research/papers"
_DEVELOPER_ENDPOINT = f"{_FIRECRAWL_BASE_URL}/search"
_SCRAPE_ENDPOINT = f"{_FIRECRAWL_BASE_URL}/scrape"
_MAP_ENDPOINT = f"{_FIRECRAWL_BASE_URL}/map"
_MAX_SEARCH_RESULTS = 10
_MAX_MAP_RESULTS = 50
_CORE_CONTENT_LIMIT = 20_000
_TIMEOUT_MS = 45_000
_SCRAPE_FORMATS = ({"type": "markdown"},)
_SCRAPE_ONLY_MAIN_CONTENT = True
_SCRAPE_SKIP_TLS_VERIFICATION = False
_SCRAPE_MAX_AGE = 0
_SCRAPE_STORE_IN_CACHE = False
_FRESHNESS_TBS = {
    Freshness.DAY: "qdr:d",
    Freshness.WEEK: "qdr:w",
    Freshness.MONTH: "qdr:m",
    Freshness.YEAR: "qdr:y",
}


class FirecrawlProvider:
    """Use only the frozen Firecrawl v2 request contracts."""

    def __init__(
        self,
        api_key: str,
        transport: ProviderTransport,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def search(
        self, operation: str, request: SearchRequest, request_id: str, deadline: float
    ) -> SearchResult:
        if operation == "papers":
            if request.freshness is not Freshness.NONE or request.domains:
                raise CoreError(request_id, ErrorCode.INVALID_REQUEST)
            payload = await self._transport.request_json(
                "GET",
                _PAPERS_ENDPOINT,
                request_id=request_id,
                headers=self._headers(),
                params={"query": request.query, "k": str(_MAX_SEARCH_RESULTS)},
                deadline=deadline,
            )
            candidates = self._papers_candidates(payload, request_id)
            sources, snippets_truncated = self._papers_sources(candidates)
        elif operation == "developer":
            body: dict[str, Any] = {
                "query": request.query,
                "limit": _MAX_SEARCH_RESULTS,
                "categories": [{"type": "developer"}],
                "timeout": _TIMEOUT_MS,
            }
            if request.domains:
                body["includeDomains"] = request.domains
            if request.freshness in _FRESHNESS_TBS:
                body["tbs"] = _FRESHNESS_TBS[request.freshness]
            payload = await self._transport.request_json(
                "POST",
                _DEVELOPER_ENDPOINT,
                request_id=request_id,
                headers=self._headers(),
                json_body=body,
                deadline=deadline,
            )
            candidates = self._developer_candidates(payload, request_id)
            sources, snippets_truncated = self._developer_sources(candidates)
        else:
            raise CoreError(request_id, ErrorCode.INVALID_REQUEST)

        if candidates and not sources:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return SearchResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if sources else ResultStatus.NO_RESULTS,
            provider=Provider.FIRECRAWL,
            direction=request.direction,
            route_used=request.route,
            retrieved_at=self._now(),
            truncated=(len(candidates) > _MAX_SEARCH_RESULTS or snippets_truncated)
            if sources
            else False,
            sources=sources[:_MAX_SEARCH_RESULTS],
        )

    async def fetch(
        self, request: FetchRequest, request_id: str, deadline: float
    ) -> FetchResult:
        if request.query:
            raise CoreError(request_id, ErrorCode.INVALID_REQUEST)
        payload = await self._transport.request_json(
            "POST",
            _SCRAPE_ENDPOINT,
            request_id=request_id,
            headers=self._headers(),
            json_body={
                "url": request.url,
                "formats": list(_SCRAPE_FORMATS),
                "onlyMainContent": _SCRAPE_ONLY_MAIN_CONTENT,
                "skipTlsVerification": _SCRAPE_SKIP_TLS_VERIFICATION,
                "timeout": _TIMEOUT_MS,
                "maxAge": _SCRAPE_MAX_AGE,
                "storeInCache": _SCRAPE_STORE_IN_CACHE,
            },
            deadline=deadline,
        )
        data = self._success_data(payload, request_id)
        metadata = data.get("metadata")
        markdown = data.get("markdown")
        final_url = metadata.get("url") if isinstance(metadata, Mapping) else None
        if not isinstance(markdown, str) or not isinstance(final_url, str):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        try:
            final_url = normalize_public_url(final_url)
        except UnsafeUrlError:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR) from None
        truncated = len(markdown) > _CORE_CONTENT_LIMIT
        content = markdown[:_CORE_CONTENT_LIMIT]
        return FetchResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if content else ResultStatus.NO_RESULTS,
            provider=Provider.FIRECRAWL,
            route_used=request.route,
            url=final_url,
            content=content,
            retrieved_at=self._now(),
            truncated=truncated if content else False,
        )

    async def map(
        self, request: MapRequest, request_id: str, deadline: float
    ) -> MapResult:
        body: dict[str, Any] = {
            "url": request.url,
            "limit": _MAX_MAP_RESULTS,
            "timeout": _TIMEOUT_MS,
        }
        if request.query:
            body["search"] = request.query
        payload = await self._transport.request_json(
            "POST",
            _MAP_ENDPOINT,
            request_id=request_id,
            headers=self._headers(),
            json_body=body,
            deadline=deadline,
        )
        links = self._links(payload, request_id)
        urls = self._map_urls(links)
        if links and not urls:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        truncated = len(urls) > _MAX_MAP_RESULTS
        urls = urls[:_MAX_MAP_RESULTS]
        return MapResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if urls else ResultStatus.NO_RESULTS,
            provider=Provider.FIRECRAWL,
            route_used=Route.PRIMARY,
            url=request.url,
            urls=urls,
            retrieved_at=self._now(),
            truncated=truncated if urls else False,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _success_data(payload: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
        if payload.get("success") is not True:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return data

    @staticmethod
    def _papers_candidates(
        payload: Mapping[str, Any], request_id: str
    ) -> list[Mapping[str, Any]]:
        if payload.get("success") is not True:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        results = payload.get("results")
        if not isinstance(results, list) or any(
            not isinstance(item, Mapping) for item in results
        ):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return results

    @staticmethod
    def _developer_candidates(
        payload: Mapping[str, Any], request_id: str
    ) -> list[Mapping[str, Any]]:
        if payload.get("success") is not True:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        data = payload.get("data")
        values = data.get("web") if isinstance(data, Mapping) else None
        if not isinstance(values, list) or any(
            not isinstance(item, Mapping) for item in values
        ):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return values

    @staticmethod
    def _links(payload: Mapping[str, Any], request_id: str) -> list[Mapping[str, Any]]:
        if payload.get("success") is not True:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        links = payload.get("links")
        if not isinstance(links, list) or any(not isinstance(item, Mapping) for item in links):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return links

    @staticmethod
    def _papers_sources(
        candidates: list[Mapping[str, Any]],
    ) -> tuple[list[SearchSource], bool]:
        sources: list[SearchSource] = []
        truncated = False
        for candidate in candidates[:_MAX_SEARCH_RESULTS]:
            try:
                primary_id = candidate.get("primaryId")
                title = candidate.get("title")
                abstract = candidate.get("abstract")
                if not isinstance(primary_id, str) or not isinstance(title, str):
                    raise TypeError("paper fields are invalid")
                if abstract is not None and not isinstance(abstract, str):
                    raise TypeError("paper abstract is invalid")
                sources.append(
                    SearchSource(
                        url=FirecrawlProvider._paper_url(primary_id),
                        title=title,
                        snippet=abstract[:2000] if abstract is not None else None,
                        source_type=SourceType.PUBLICATION,
                    )
                )
                truncated = truncated or (
                    abstract is not None and len(abstract) > 2000
                )
            except (UnsafeUrlError, ValidationError, TypeError, ValueError):
                continue
        return sources, truncated

    @staticmethod
    def _developer_sources(
        candidates: list[Mapping[str, Any]],
    ) -> tuple[list[SearchSource], bool]:
        sources: list[SearchSource] = []
        truncated = False
        for candidate in candidates[:_MAX_SEARCH_RESULTS]:
            try:
                url = candidate.get("url")
                title = candidate.get("title")
                description = candidate.get("description")
                if not isinstance(url, str) or not isinstance(title, str):
                    raise TypeError("developer result fields are invalid")
                if description is not None and not isinstance(description, str):
                    raise TypeError("developer result description is invalid")
                sources.append(
                    SearchSource(
                        url=url,
                        title=title,
                        snippet=description[:2000] if description is not None else None,
                        source_type=SourceType.DEVELOPER,
                    )
                )
                truncated = truncated or (
                    description is not None and len(description) > 2000
                )
            except (UnsafeUrlError, ValidationError, TypeError, ValueError):
                continue
        return sources, truncated

    @staticmethod
    def _paper_url(primary_id: str) -> str:
        prefix, separator, value = primary_id.partition(":")
        if not separator or not value:
            raise ValueError("unknown paper identifier")
        if prefix == "arxiv":
            url = f"https://arxiv.org/abs/{quote(value, safe='')}"
        elif prefix == "pmid":
            url = f"https://pubmed.ncbi.nlm.nih.gov/{quote(value, safe='')}/"
        elif prefix == "pmcid":
            url = f"https://pmc.ncbi.nlm.nih.gov/articles/{quote(value, safe='')}/"
        elif prefix == "doi":
            url = f"https://doi.org/{quote(value, safe='/')}"
        elif prefix == "web":
            url = value
        else:
            raise ValueError("unknown paper identifier")
        return normalize_public_url(url)

    @staticmethod
    def _map_urls(links: list[Mapping[str, Any]]) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for link in links:
            try:
                value = link.get("url")
                if not isinstance(value, str):
                    raise TypeError("map URL is invalid")
                url = normalize_public_url(value)
            except (UnsafeUrlError, TypeError, ValueError):
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls
