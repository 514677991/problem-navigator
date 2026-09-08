"""Strict, transport-independent models for the research core."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .security import normalize_public_hostname, normalize_public_url


class _StringEnum(str, Enum):
    """A JSON-friendly closed string enum."""


class Direction(_StringEnum):
    AUTO = "auto"
    NEWS = "news"
    SEMANTIC = "semantic"
    ACADEMIC = "academic"
    DEVELOPER = "developer"


class Route(_StringEnum):
    PRIMARY = "primary"
    ALTERNATE = "alternate"


class Freshness(_StringEnum):
    NONE = ""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class ResultStatus(_StringEnum):
    SUCCESS = "SUCCESS"
    NO_RESULTS = "NO_RESULTS"


class ErrorCode(_StringEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class Provider(_StringEnum):
    BRAVE = "brave"
    EXA = "exa"
    FIRECRAWL = "firecrawl"


class SourceType(_StringEnum):
    WEB = "web"
    NEWS = "news"
    PUBLICATION = "publication"
    DEVELOPER = "developer"


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def validate_request_id(value: str) -> str:
    if not isinstance(value, str) or not REQUEST_ID_PATTERN.fullmatch(value):
        raise ValueError("request ID must use 16-64 URL-safe characters")
    return value


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Domain = Annotated[str, Field(min_length=1, max_length=253)]


class StatusRequest(_StrictModel):
    """The status tool deliberately accepts no input fields."""


class SearchRequest(_StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    direction: Direction = Direction.AUTO
    route: Route = Route.PRIMARY
    freshness: Freshness = Freshness.NONE
    domains: list[Domain] = Field(default=[], max_length=20)

    @field_validator("query")
    @classmethod
    def _query_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

    @field_validator("domains")
    @classmethod
    def _domains_are_public_hostnames(cls, values: list[str]) -> list[str]:
        return [normalize_public_hostname(value) for value in values]


class FetchRequest(_StrictModel):
    url: str = Field(min_length=1, max_length=8192)
    query: str = Field(default="", max_length=2000)
    route: Route = Route.PRIMARY

    @field_validator("url")
    @classmethod
    def _url_is_public(cls, value: str) -> str:
        return normalize_public_url(value)


class MapRequest(_StrictModel):
    url: str = Field(min_length=1, max_length=8192)
    query: str = Field(default="", max_length=2000)

    @field_validator("url")
    @classmethod
    def _url_is_public(cls, value: str) -> str:
        return normalize_public_url(value)


class SearchSource(_StrictModel):
    url: str
    title: str
    snippet: str | None = Field(default=None, max_length=2000)
    published_at: datetime | None = None
    source_type: SourceType

    @field_validator("url")
    @classmethod
    def _url_is_public(cls, value: str) -> str:
        return normalize_public_url(value)

    @field_validator("published_at")
    @classmethod
    def _published_at_is_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("published_at must include a timezone")
        return value.astimezone(timezone.utc)


class _ResultBase(_StrictModel):
    request_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]{16,64}$",
    )
    status: ResultStatus
    retrieved_at: datetime
    truncated: bool

    @field_validator("request_id")
    @classmethod
    def _request_id_is_valid(cls, value: str) -> str:
        return validate_request_id(value)

    @field_validator("retrieved_at")
    @classmethod
    def _retrieved_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        return value.astimezone(timezone.utc)


class SearchResult(_ResultBase):
    provider: Provider
    direction: Direction
    route_used: Route
    sources: list[SearchSource] = Field(max_length=10)

    @model_validator(mode="after")
    def _status_matches_sources(self) -> "SearchResult":
        if self.status is ResultStatus.SUCCESS and not self.sources:
            raise ValueError("SUCCESS search results need at least one source")
        if self.status is ResultStatus.NO_RESULTS and (self.sources or self.truncated):
            raise ValueError("NO_RESULTS search results must be empty and untruncated")
        return self


class FetchResult(_ResultBase):
    provider: Literal[Provider.FIRECRAWL, Provider.EXA]
    route_used: Route
    url: str
    content: str = Field(max_length=20000)

    @field_validator("url")
    @classmethod
    def _url_is_public(cls, value: str) -> str:
        return normalize_public_url(value)

    @model_validator(mode="after")
    def _status_matches_content(self) -> "FetchResult":
        if self.status is ResultStatus.SUCCESS and not self.content:
            raise ValueError("SUCCESS fetch results need content")
        if self.status is ResultStatus.NO_RESULTS and (self.content or self.truncated):
            raise ValueError("NO_RESULTS fetch results must be empty and untruncated")
        return self


class MapResult(_ResultBase):
    provider: Literal[Provider.FIRECRAWL]
    route_used: Literal[Route.PRIMARY]
    url: str
    urls: list[str] = Field(max_length=50)

    @field_validator("url")
    @classmethod
    def _url_is_public(cls, value: str) -> str:
        return normalize_public_url(value)

    @field_validator("urls")
    @classmethod
    def _urls_are_public(cls, values: list[str]) -> list[str]:
        return [normalize_public_url(value) for value in values]

    @model_validator(mode="after")
    def _status_matches_urls(self) -> "MapResult":
        if self.status is ResultStatus.SUCCESS and not self.urls:
            raise ValueError("SUCCESS map results need at least one URL")
        if self.status is ResultStatus.NO_RESULTS and (self.urls or self.truncated):
            raise ValueError("NO_RESULTS map results must be empty and untruncated")
        return self


_ERROR_MESSAGES = {
    ErrorCode.INVALID_REQUEST: "Request is invalid.",
    ErrorCode.NOT_CONFIGURED: "Selected route is not configured.",
    ErrorCode.AUTH_FAILED: "Selected route authentication failed.",
    ErrorCode.RATE_LIMITED: "Selected route is rate limited.",
    ErrorCode.QUOTA_EXHAUSTED: "Selected route quota is exhausted.",
    ErrorCode.NETWORK_ERROR: "Selected route network request failed.",
    ErrorCode.PROVIDER_ERROR: "Selected route provider failed.",
}


class CoreError(Exception):
    """A safe, fixed-shape error that never serializes provider details."""

    def __init__(self, request_id: str, code: ErrorCode) -> None:
        self.request_id = validate_request_id(request_id)
        self.code = ErrorCode(code)
        super().__init__(self.message)

    @property
    def message(self) -> str:
        """Return the fixed summary for the error's current code."""
        return _ERROR_MESSAGES[self.code]

    def as_dict(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "code": self.code.value,
            "message": _ERROR_MESSAGES[self.code],
        }


def safe_error_message(code: ErrorCode) -> str:
    return _ERROR_MESSAGES[ErrorCode(code)]
