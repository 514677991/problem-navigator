"""Fixed-contract Brave Search adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from ..models import (
    CoreError,
    ErrorCode,
    Freshness,
    Provider,
    ResultStatus,
    SearchRequest,
    SearchResult,
    SearchSource,
    SourceType,
)
from ..security import UnsafeUrlError
from .base import ProviderTransport


_BRAVE_BASE_URL = "https://api.search.brave.com"
BRAVE_OPERATIONS: dict[str, tuple[str, dict[str, str], SourceType]] = {
    "llm_context": (
        "/res/v1/llm/context",
        {"count": "10", "maximum_number_of_urls": "10", "maximum_number_of_tokens": "8192"},
        SourceType.WEB,
    ),
    "news": ("/res/v1/news/search", {"count": "10"}, SourceType.NEWS),
    "web": ("/res/v1/web/search", {"count": "10"}, SourceType.DEVELOPER),
}
_FRESHNESS = {
    Freshness.DAY: "pd",
    Freshness.WEEK: "pw",
    Freshness.MONTH: "pm",
    Freshness.YEAR: "py",
}


class BraveProvider:
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
        if (
            operation not in BRAVE_OPERATIONS
            or len(request.query) > 400
            or len(request.query.split()) > 50
            or request.domains
        ):
            raise CoreError(request_id, ErrorCode.INVALID_REQUEST)
        path, fixed_params, source_type = BRAVE_OPERATIONS[operation]
        params = {"q": request.query, **fixed_params}
        if request.freshness in _FRESHNESS:
            params["freshness"] = _FRESHNESS[request.freshness]
        payload = await self._transport.request_json(
            "GET",
            _BRAVE_BASE_URL + path,
            request_id=request_id,
            headers={
                "X-Subscription-Token": self._api_key,
                "Accept": "application/json",
                "Api-Version": "2026-02-06",
            },
            params=params,
            deadline=deadline,
        )
        candidates = self._candidates(operation, payload, request_id)
        sources: list[SearchSource] = []
        snippets_truncated = False
        for candidate in candidates[:10]:
            try:
                source, snippet_truncated = self._source(
                    operation, candidate, source_type
                )
                sources.append(source)
                snippets_truncated = snippets_truncated or snippet_truncated
            except (UnsafeUrlError, ValidationError, TypeError, ValueError):
                continue
        if candidates and not sources:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return SearchResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if sources else ResultStatus.NO_RESULTS,
            provider=Provider.BRAVE,
            direction=request.direction,
            route_used=request.route,
            retrieved_at=now.astimezone(timezone.utc),
            truncated=(len(candidates) > 10 or snippets_truncated) if sources else False,
            sources=sources,
        )

    @staticmethod
    def _candidates(
        operation: str, payload: Mapping[str, Any], request_id: str
    ) -> list[Mapping[str, Any]]:
        if operation == "llm_context":
            grounding = payload.get("grounding")
            values = grounding.get("generic") if isinstance(grounding, Mapping) else None
        elif operation == "news":
            values = payload.get("results")
        else:
            web = payload.get("web")
            values = web.get("results") if isinstance(web, Mapping) else None
        if not isinstance(values, list) or any(not isinstance(value, Mapping) for value in values):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return values

    @staticmethod
    def _source(
        operation: str, item: Mapping[str, Any], source_type: SourceType
    ) -> tuple[SearchSource, bool]:
        url = item.get("url")
        title = item.get("title")
        if not isinstance(url, str) or not isinstance(title, str):
            raise TypeError("source URL and title must be strings")
        if operation == "llm_context":
            snippets = item.get("snippets")
            if not isinstance(snippets, list) or any(not isinstance(value, str) for value in snippets):
                raise TypeError("LLM snippets must be string array")
            raw_snippet = "".join(snippets)
            snippet = raw_snippet[:2000]
            published_at = None
        else:
            description = item.get("description", "")
            if not isinstance(description, str):
                raise TypeError("description must be text")
            raw_snippet = description
            snippet = raw_snippet[:2000]
            published_at = item.get("page_age") if operation == "news" else None
        return (
            SearchSource(
                url=url,
                title=title,
                snippet=snippet,
                published_at=published_at,
                source_type=source_type,
            ),
            len(raw_snippet) > 2000,
        )
