"""Fixed-contract Exa Search and Contents adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from ..models import (
    CoreError,
    ErrorCode,
    FetchRequest,
    FetchResult,
    Freshness,
    Provider,
    ResultStatus,
    SearchRequest,
    SearchResult,
    SearchSource,
    SourceType,
)
from ..security import UnsafeUrlError, normalize_public_url
from .base import ProviderTransport


_EXA_BASE_URL = "https://api.exa.ai"
_SEARCH_OPERATIONS: dict[str, tuple[str | None, SourceType]] = {
    "search_auto": (None, SourceType.WEB),
    "news": ("news", SourceType.NEWS),
    "publication": ("publication", SourceType.PUBLICATION),
}
_FRESHNESS_DAYS = {
    Freshness.DAY: 1,
    Freshness.WEEK: 7,
    Freshness.MONTH: 31,
    Freshness.YEAR: 365,
}
_MAX_RESULTS = 10
_MAX_SNIPPET_CHARACTERS = 2_000
_MAX_CONTENT_CHARACTERS = 10_000
_CORE_CONTENT_LIMIT = 20_000


class ExaProvider:
    """Use only the frozen Exa Search and Contents request contracts."""

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
        mapping = _SEARCH_OPERATIONS.get(operation)
        if mapping is None:
            raise CoreError(request_id, ErrorCode.INVALID_REQUEST)
        category, source_type = mapping
        body: dict[str, Any] = {
            "query": request.query,
            "type": "auto",
            "numResults": _MAX_RESULTS,
            "contents": {"highlights": {"maxCharacters": _MAX_SNIPPET_CHARACTERS}},
        }
        if category is not None:
            body["category"] = category
        if request.domains:
            body["includeDomains"] = request.domains
        if request.freshness in _FRESHNESS_DAYS:
            body["startPublishedDate"] = self._iso_utc(
                self._now() - timedelta(days=_FRESHNESS_DAYS[request.freshness])
            )
        payload = await self._transport.request_json(
            "POST",
            f"{_EXA_BASE_URL}/search",
            request_id=request_id,
            headers={"x-api-key": self._api_key},
            json_body=body,
            deadline=deadline,
        )
        candidates = self._search_candidates(payload, request_id)
        sources: list[SearchSource] = []
        snippets_truncated = False
        for candidate in candidates[:_MAX_RESULTS]:
            try:
                source, snippet_truncated = self._search_source(candidate, source_type)
                sources.append(source)
                snippets_truncated = snippets_truncated or snippet_truncated
            except (UnsafeUrlError, ValidationError, TypeError, ValueError):
                continue
        if candidates and not sources:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return SearchResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if sources else ResultStatus.NO_RESULTS,
            provider=Provider.EXA,
            direction=request.direction,
            route_used=request.route,
            retrieved_at=self._now(),
            truncated=(len(candidates) > _MAX_RESULTS or snippets_truncated)
            if sources
            else False,
            sources=sources,
        )

    async def fetch(
        self, request: FetchRequest, request_id: str, deadline: float
    ) -> FetchResult:
        body: dict[str, Any] = {"urls": [request.url]}
        if request.query:
            body["highlights"] = {
                "query": request.query,
                "maxCharacters": _MAX_CONTENT_CHARACTERS,
            }
        else:
            body["text"] = {"maxCharacters": _MAX_CONTENT_CHARACTERS}
        payload = await self._transport.request_json(
            "POST",
            f"{_EXA_BASE_URL}/contents",
            request_id=request_id,
            headers={"x-api-key": self._api_key},
            json_body=body,
            deadline=deadline,
        )
        record = self._matched_contents_record(payload, request.url, request_id)
        content = self._contents_content(record, request.query, request_id)
        truncated = bool(content) and (
            bool(request.query)
            or len(content) >= _MAX_CONTENT_CHARACTERS
            or len(content) > _CORE_CONTENT_LIMIT
        )
        content = content[:_CORE_CONTENT_LIMIT]
        return FetchResult(
            request_id=request_id,
            status=ResultStatus.SUCCESS if content else ResultStatus.NO_RESULTS,
            provider=Provider.EXA,
            route_used=request.route,
            url=request.url,
            content=content,
            retrieved_at=self._now(),
            truncated=truncated if content else False,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _iso_utc(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _search_candidates(
        payload: Mapping[str, Any], request_id: str
    ) -> list[Mapping[str, Any]]:
        values = payload.get("results")
        if not isinstance(values, list) or any(not isinstance(value, Mapping) for value in values):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return values

    @staticmethod
    def _search_source(
        item: Mapping[str, Any], source_type: SourceType
    ) -> tuple[SearchSource, bool]:
        url = item.get("url")
        title = item.get("title")
        highlights = item.get("highlights")
        published_date = item.get("publishedDate")
        if not isinstance(url, str) or not isinstance(title, str):
            raise TypeError("Exa search sources need string URLs and titles")
        if highlights is not None:
            if not isinstance(highlights, list) or any(
                not isinstance(value, str) for value in highlights
            ):
                raise TypeError("Exa search highlights must be a string array")
            raw_snippet = "\n\n".join(highlights)
            snippet_truncated = len(raw_snippet) >= _MAX_SNIPPET_CHARACTERS
        else:
            text = item.get("text")
            if text is not None and not isinstance(text, str):
                raise TypeError("Exa search source text must be a string")
            raw_snippet = text
            snippet_truncated = (
                raw_snippet is not None
                and len(raw_snippet) > _MAX_SNIPPET_CHARACTERS
            )
        if published_date is not None and not isinstance(published_date, str):
            raise TypeError("Exa search published date must be a string")
        return (
            SearchSource(
                url=url,
                title=title,
                snippet=(
                    raw_snippet[:_MAX_SNIPPET_CHARACTERS]
                    if raw_snippet is not None
                    else None
                ),
                published_at=published_date,
                source_type=source_type,
            ),
            snippet_truncated,
        )

    @staticmethod
    def _matched_contents_record(
        payload: Mapping[str, Any], requested_url: str, request_id: str
    ) -> Mapping[str, Any]:
        results = payload.get("results")
        statuses = payload.get("statuses")
        if (
            not isinstance(results, list)
            or not isinstance(statuses, list)
            or any(not isinstance(value, Mapping) for value in results)
            or any(not isinstance(value, Mapping) for value in statuses)
            or len(results) != 1
            or len(statuses) != 1
        ):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        for status in statuses:
            ExaProvider._record_url(status, request_id)
            if not isinstance(status.get("status"), str):
                raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        for result in results:
            ExaProvider._record_url(result, request_id)
        matching_statuses = [
            status
            for status in statuses
            if ExaProvider._record_url(status, request_id) == requested_url
        ]
        if len(matching_statuses) != 1 or matching_statuses[0].get("status") != "success":
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        matching_results = [
            result
            for result in results
            if ExaProvider._record_url(result, request_id) == requested_url
        ]
        if len(matching_results) != 1:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return matching_results[0]

    @staticmethod
    def _record_url(record: Mapping[str, Any], request_id: str) -> str:
        url = record.get("url")
        if not isinstance(url, str):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        try:
            return normalize_public_url(url)
        except UnsafeUrlError:
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR) from None

    @staticmethod
    def _contents_content(record: Mapping[str, Any], query: str, request_id: str) -> str:
        if not query:
            text = record.get("text")
            if not isinstance(text, str):
                raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
            return text
        highlights = record.get("highlights")
        if not isinstance(highlights, list) or any(
            not isinstance(value, str) for value in highlights
        ):
            raise CoreError(request_id, ErrorCode.PROVIDER_ERROR)
        return "\n\n".join(highlights)
