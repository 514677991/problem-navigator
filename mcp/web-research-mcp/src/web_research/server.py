"""Thin stdio MCP surface for the protocol-independent research core."""

from __future__ import annotations

import asyncio
import json
import math
import secrets
import time
from collections.abc import Callable
from typing import Annotated, Any, Protocol

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import Field

from .config import ConfigSnapshot, StatusResult, configuration_status, load_config
from .core import ResearchCore
from .models import (
    CoreError,
    Direction,
    Domain,
    ErrorCode,
    FetchRequest,
    FetchResult,
    Freshness,
    MapRequest,
    MapResult,
    Route,
    SearchRequest,
    SearchResult,
    StatusRequest,
)
from .providers import ProviderTransport


SERVER_ID = "web-research"
NETWORK_CALLS_PER_MINUTE = 60
MAX_CONCURRENT_NETWORK_CALLS = 2

SearchQuery = Annotated[str, Field(min_length=1, max_length=2_000)]
OptionalQuery = Annotated[str, Field(max_length=2_000)]
PublicUrl = Annotated[str, Field(min_length=1, max_length=8_192)]
Domains = Annotated[list[Domain], Field(max_length=20)]


class _Core(Protocol):
    async def search(self, query: str, **kwargs: Any) -> SearchResult: ...
    async def fetch(self, url: str, **kwargs: Any) -> FetchResult: ...
    async def map(self, url: str, **kwargs: Any) -> MapResult: ...


class FixedWindowLimiter:
    """A process-local counter for aligned monotonic sixty-second buckets."""

    def __init__(
        self,
        limit: int = NETWORK_CALLS_PER_MINUTE,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._monotonic = monotonic
        self._bucket: int | None = None
        self._count = 0

    def allow(self) -> bool:
        bucket = math.floor(self._monotonic() / 60.0)
        if bucket != self._bucket:
            self._bucket = bucket
            self._count = 0
        if self._count >= self._limit:
            return False
        self._count += 1
        return True


def _tool_error(error: CoreError) -> ToolError:
    return ToolError(
        json.dumps(error.as_dict(), ensure_ascii=False, separators=(",", ":"))
    )


def _rate_limit_error() -> ToolError:
    return _tool_error(CoreError(secrets.token_urlsafe(18), ErrorCode.RATE_LIMITED))


def create_server(
    *,
    core_factory: Callable[[ConfigSnapshot], _Core],
    snapshot_loader: Callable[[], ConfigSnapshot] = load_config,
    monotonic: Callable[[], float] = time.monotonic,
) -> FastMCP:
    """Create a resource-free server around a caller-owned core factory."""
    server = FastMCP(SERVER_ID)
    limiter = FixedWindowLimiter(monotonic=monotonic)
    network_gate = asyncio.Semaphore(MAX_CONCURRENT_NETWORK_CALLS)

    def current_core() -> _Core:
        snapshot = snapshot_loader()
        return core_factory(snapshot)

    async def status_handler() -> StatusResult:
        return configuration_status(snapshot_loader())

    async def search_handler(
        query: SearchQuery,
        direction: Direction = Direction.AUTO,
        route: Route = Route.PRIMARY,
        freshness: Freshness = Freshness.NONE,
        domains: Domains = [],
    ) -> SearchResult:
        if not limiter.allow():
            raise _rate_limit_error()
        try:
            async with network_gate:
                return await current_core().search(
                    query,
                    direction=direction,
                    route=route,
                    freshness=freshness,
                    domains=domains,
                )
        except CoreError as error:
            raise _tool_error(error) from None

    async def fetch_handler(
        url: PublicUrl,
        query: OptionalQuery = "",
        route: Route = Route.PRIMARY,
    ) -> FetchResult:
        if not limiter.allow():
            raise _rate_limit_error()
        try:
            async with network_gate:
                return await current_core().fetch(url, query=query, route=route)
        except CoreError as error:
            raise _tool_error(error) from None

    async def map_handler(url: PublicUrl, query: OptionalQuery = "") -> MapResult:
        if not limiter.allow():
            raise _rate_limit_error()
        try:
            async with network_gate:
                return await current_core().map(url, query=query)
        except CoreError as error:
            raise _tool_error(error) from None

    offline_annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    network_annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
    tools = (
        FunctionTool(
            name="web_research_status",
            description="Report local provider configuration without network access.",
            fn=status_handler,
            return_type=StatusResult,
            parameters=StatusRequest.model_json_schema(),
            output_schema=StatusResult.model_json_schema(),
            annotations=offline_annotations,
            run_in_thread=False,
        ),
        FunctionTool(
            name="web_search",
            description="Search public Web sources through one explicitly selected route.",
            fn=search_handler,
            return_type=SearchResult,
            parameters=SearchRequest.model_json_schema(),
            output_schema=SearchResult.model_json_schema(),
            annotations=network_annotations,
            run_in_thread=False,
        ),
        FunctionTool(
            name="web_fetch",
            description="Fetch one public URL through one explicitly selected route.",
            fn=fetch_handler,
            return_type=FetchResult,
            parameters=FetchRequest.model_json_schema(),
            output_schema=FetchResult.model_json_schema(),
            annotations=network_annotations,
            run_in_thread=False,
        ),
        FunctionTool(
            name="web_map",
            description="Discover public URLs beneath one public starting URL.",
            fn=map_handler,
            return_type=MapResult,
            parameters=MapRequest.model_json_schema(),
            output_schema=MapResult.model_json_schema(),
            annotations=network_annotations,
            run_in_thread=False,
        ),
    )
    for tool in tools:
        server.add_tool(tool)
    return server


async def _run_stdio(
    *,
    http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient,
    server_factory: Callable[..., FastMCP] = create_server,
) -> None:
    """Own the one HTTP client for the lifetime of the stdio process."""
    client = http_client_factory()
    try:
        transport = ProviderTransport(client)

        def core_factory(snapshot: ConfigSnapshot) -> ResearchCore:
            return ResearchCore.from_config(snapshot, transport=transport)

        server = server_factory(core_factory=core_factory)
        await server.run_async(transport="stdio", show_banner=False)
    finally:
        await client.aclose()


def main() -> None:
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
