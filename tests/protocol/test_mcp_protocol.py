from __future__ import annotations

import asyncio
import inspect
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from jsonschema import Draft202012Validator, ValidationError as JsonSchemaValidationError

from web_research import server as server_module
from web_research.config import ConfigSnapshot
from web_research.core import ResearchCore
from web_research.models import (
    CoreError,
    ErrorCode,
    FetchResult,
    MapResult,
    SearchResult,
    SearchSource,
)
from web_research.server import create_server


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
REQUEST_ID = "protocol-call-id1"
EXPECTED_TOOLS = {
    "web_research_status",
    "web_search",
    "web_fetch",
    "web_map",
}


class SuccessfulCore:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, **kwargs: Any) -> SearchResult:
        self.calls += 1
        return SearchResult(
            request_id=REQUEST_ID,
            status="SUCCESS",
            provider="brave",
            direction=kwargs.get("direction", "auto"),
            route_used=kwargs.get("route", "primary"),
            retrieved_at=NOW,
            truncated=False,
            sources=[
                SearchSource(
                    url="https://example.com/source",
                    title=query,
                    source_type="web",
                )
            ],
        )

    async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        self.calls += 1
        return FetchResult(
            request_id=REQUEST_ID,
            status="SUCCESS",
            provider="firecrawl",
            route_used=kwargs.get("route", "primary"),
            url=url,
            content="content",
            retrieved_at=NOW,
            truncated=False,
        )

    async def map(self, url: str, **kwargs: Any) -> MapResult:
        self.calls += 1
        return MapResult(
            request_id=REQUEST_ID,
            status="SUCCESS",
            provider="firecrawl",
            route_used="primary",
            url=url,
            urls=["https://example.com/source"],
            retrieved_at=NOW,
            truncated=False,
        )


class InvalidRequestCore(SuccessfulCore):
    async def search(self, query: str, **kwargs: Any) -> SearchResult:
        raise CoreError(REQUEST_ID, ErrorCode.INVALID_REQUEST)


def _server(core: object, *, monotonic: Any = lambda: 0.0):
    return create_server(
        snapshot_loader=lambda: ConfigSnapshot(),
        core_factory=lambda _snapshot: core,
        monotonic=monotonic,
    )


def _tool_error_payload(exc: ToolError) -> dict[str, str]:
    return json.loads(str(exc))


def test_four_tools_have_strict_input_output_schemas_and_annotations() -> None:
    async def exercise() -> None:
        tools = await _server(SuccessfulCore()).list_tools()
        by_name = {tool.name: tool for tool in tools}

        assert set(by_name) == EXPECTED_TOOLS
        for tool in by_name.values():
            assert tool.parameters["additionalProperties"] is False
            assert tool.output_schema is not None
            assert tool.output_schema["type"] == "object"
            assert tool.output_schema["additionalProperties"] is False
            assert tool.output_schema.get("properties")

        search = by_name["web_search"]
        properties = search.parameters["properties"]
        assert properties["query"]["minLength"] == 1
        assert properties["query"]["maxLength"] == 2000
        assert properties["direction"]["default"] == "auto"
        assert properties["route"]["default"] == "primary"
        assert properties["freshness"]["default"] == ""
        assert properties["domains"]["default"] == []
        assert properties["domains"]["maxItems"] == 20
        assert properties["domains"]["items"]["minLength"] == 1
        assert properties["domains"]["items"]["maxLength"] == 253
        assert properties["direction"]["enum"] == [
            "auto", "news", "semantic", "academic", "developer"
        ]
        assert properties["route"]["enum"] == ["primary", "alternate"]
        assert properties["freshness"]["enum"] == [
            "", "day", "week", "month", "year"
        ]
        assert search.annotations.read_only_hint is True
        assert search.annotations.destructive_hint is False
        assert search.annotations.idempotent_hint is False
        assert search.annotations.open_world_hint is True

        status = by_name["web_research_status"]
        assert status.parameters["additionalProperties"] is False
        assert status.parameters["properties"] == {}
        assert status.parameters["type"] == "object"
        assert status.annotations.read_only_hint is True
        assert status.annotations.destructive_hint is False
        assert status.annotations.idempotent_hint is True
        assert status.annotations.open_world_hint is False

    asyncio.run(exercise())


def test_network_output_schemas_enforce_request_id_pattern_and_lengths() -> None:
    async def exercise() -> None:
        tools = {tool.name: tool for tool in await _server(SuccessfulCore()).list_tools()}
        payloads = {
            "web_search": SearchResult(
                request_id=REQUEST_ID,
                status="SUCCESS",
                provider="brave",
                direction="auto",
                route_used="primary",
                retrieved_at=NOW,
                truncated=False,
                sources=[
                    SearchSource(
                        url="https://example.com/source",
                        title="source",
                        source_type="web",
                    )
                ],
            ).model_dump(mode="json"),
            "web_fetch": FetchResult(
                request_id=REQUEST_ID,
                status="SUCCESS",
                provider="firecrawl",
                route_used="primary",
                url="https://example.com",
                content="content",
                retrieved_at=NOW,
                truncated=False,
            ).model_dump(mode="json"),
            "web_map": MapResult(
                request_id=REQUEST_ID,
                status="SUCCESS",
                provider="firecrawl",
                route_used="primary",
                url="https://example.com",
                urls=["https://example.com/source"],
                retrieved_at=NOW,
                truncated=False,
            ).model_dump(mode="json"),
        }
        for name, payload in payloads.items():
            schema = tools[name].output_schema
            request_id_schema = schema["properties"]["request_id"]
            assert request_id_schema == {
                "maxLength": 64,
                "minLength": 16,
                "pattern": "^[A-Za-z0-9_-]{16,64}$",
                "title": "Request Id",
                "type": "string",
            }
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(payload)
            invalid = deepcopy(payload)
            invalid["request_id"] = "too-short"
            with pytest.raises(JsonSchemaValidationError):
                Draft202012Validator(schema).validate(invalid)

    asyncio.run(exercise())


class TrackingHttpClient:
    def __init__(self) -> None:
        self.close_calls = 0

    async def aclose(self) -> None:
        self.close_calls += 1


class RecordingStdioServer:
    def __init__(self, outcome: str = "return") -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, bool]] = []
        self.entered = asyncio.Event()

    async def run_async(self, *, transport: str, show_banner: bool) -> None:
        self.calls.append((transport, show_banner))
        self.entered.set()
        if self.outcome == "raise":
            raise RuntimeError("stdio failed")
        if self.outcome == "block":
            await asyncio.Event().wait()


def _run_stdio_fixture(outcome: str = "return") -> tuple[
    TrackingHttpClient, RecordingStdioServer, Any, Any
]:
    client = TrackingHttpClient()
    server = RecordingStdioServer(outcome)

    def client_factory() -> TrackingHttpClient:
        return client

    def server_factory(*, core_factory: Any) -> RecordingStdioServer:
        assert callable(core_factory)
        return server

    return client, server, client_factory, server_factory


def test_create_server_requires_an_injected_core_factory() -> None:
    with pytest.raises(TypeError):
        create_server()


@pytest.mark.parametrize("first_to_exit", [0, 1])
def test_overlapping_clients_survive_either_exit_order_without_resource_ownership(
    first_to_exit: int,
) -> None:
    core = SuccessfulCore()
    server = _server(core)

    async def exercise() -> None:
        clients = [Client(server), Client(server)]
        await clients[0].__aenter__()
        await clients[1].__aenter__()
        try:
            await clients[first_to_exit].__aexit__(None, None, None)
            remaining = clients[1 - first_to_exit]
            result = await remaining.call_tool(
                "web_search", {"query": "still active"}, raise_on_error=False
            )
            assert result.is_error is False
        finally:
            await clients[1 - first_to_exit].__aexit__(None, None, None)

    asyncio.run(exercise())


def test_overlapping_clients_share_the_server_rate_limiter() -> None:
    core = SuccessfulCore()
    server = _server(core)

    async def exercise() -> None:
        first = Client(server)
        second = Client(server)
        await first.__aenter__()
        await second.__aenter__()
        try:
            for index in range(60):
                active = first if index % 2 == 0 else second
                result = await active.call_tool(
                    "web_search", {"query": "shared window"}, raise_on_error=False
                )
                assert result.is_error is False
            limited = await second.call_tool(
                "web_search", {"query": "sixty first"}, raise_on_error=False
            )
            assert limited.is_error is True
            assert json.loads(limited.content[0].text)["code"] == "RATE_LIMITED"
        finally:
            await first.__aexit__(None, None, None)
            await second.__aexit__(None, None, None)

    asyncio.run(exercise())


def test_stdio_runner_owns_one_client_and_closes_once_on_normal_return() -> None:
    client, server, client_factory, server_factory = _run_stdio_fixture()

    asyncio.run(
        server_module._run_stdio(
            http_client_factory=client_factory,
            server_factory=server_factory,
        )
    )

    assert server.calls == [("stdio", False)]
    assert client.close_calls == 1


def test_stdio_runner_closes_client_once_when_server_raises() -> None:
    client, server, client_factory, server_factory = _run_stdio_fixture("raise")

    with pytest.raises(RuntimeError, match="stdio failed"):
        asyncio.run(
            server_module._run_stdio(
                http_client_factory=client_factory,
                server_factory=server_factory,
            )
        )

    assert server.calls == [("stdio", False)]
    assert client.close_calls == 1


def test_stdio_runner_closes_client_once_when_cancelled() -> None:
    client, server, client_factory, server_factory = _run_stdio_fixture("block")


    async def exercise() -> None:
        task = asyncio.create_task(
            server_module._run_stdio(
                http_client_factory=client_factory,
                server_factory=server_factory,
            )
        )
        await asyncio.wait_for(server.entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert server.calls == [("stdio", False)]
    assert client.close_calls == 1


def test_success_has_matching_text_and_structured_content_and_error_has_safe_text_only() -> None:
    async def exercise() -> None:
        success_server = _server(SuccessfulCore())
        async with Client(success_server) as client:
            success = await client.call_tool(
                "web_search", {"query": "evidence"}, raise_on_error=False
            )
        assert success.is_error is False
        assert len(success.content) == 1
        assert json.loads(success.content[0].text) == success.structured_content
        assert SearchResult.model_validate(success.structured_content)

        error_server = _server(InvalidRequestCore())
        async with Client(error_server) as client:
            failure = await client.call_tool(
                "web_search", {"query": "evidence"}, raise_on_error=False
            )
        assert failure.is_error is True
        assert failure.structured_content is None
        assert len(failure.content) == 1
        assert json.loads(failure.content[0].text) == {
            "request_id": REQUEST_ID,
            "code": "INVALID_REQUEST",
            "message": "Request is invalid.",
        }

    asyncio.run(exercise())


def test_status_succeeds_offline_and_unconfigured_search_is_tool_error() -> None:
    server = create_server(
        snapshot_loader=lambda: ConfigSnapshot(),
        core_factory=lambda _snapshot: ResearchCore({}),
        monotonic=lambda: 0.0,
    )

    async def exercise() -> None:
        async with Client(server) as client:
            status = await client.call_tool(
                "web_research_status", {}, raise_on_error=False
            )
            search = await client.call_tool(
                "web_search", {"query": "must-not-hit-network"}, raise_on_error=False
            )
        assert status.is_error is False
        assert status.structured_content["config_state"] == "NOT_CONFIGURED"
        assert status.structured_content["capabilities"]["search"] == "NOT_CONFIGURED"
        assert search.is_error is True
        assert json.loads(search.content[0].text)["code"] == "NOT_CONFIGURED"

    asyncio.run(exercise())


def test_first_sixty_network_calls_succeed_and_sixty_first_is_rate_limited() -> None:
    core = SuccessfulCore()
    server = _server(core)

    async def exercise() -> None:
        network_calls = (
            ("web_search", {"query": "evidence"}),
            ("web_fetch", {"url": "https://example.com"}),
            ("web_map", {"url": "https://example.com"}),
        )
        for index in range(60):
            name, arguments = network_calls[index % len(network_calls)]
            result = await server.call_tool(name, arguments)
            assert result.is_error is False
        with pytest.raises(ToolError) as raised:
            await server.call_tool("web_search", {"query": "evidence"})
        assert _tool_error_payload(raised.value)["code"] == "RATE_LIMITED"

    asyncio.run(exercise())
    assert core.calls == 60


def test_fixed_window_resets_at_next_aligned_minute() -> None:
    clock = [59.999]
    core = SuccessfulCore()
    server = _server(core, monotonic=lambda: clock[0])

    async def exercise() -> None:
        for _ in range(60):
            await server.call_tool("web_search", {"query": "evidence"})
        with pytest.raises(ToolError):
            await server.call_tool("web_search", {"query": "evidence"})
        clock[0] = 60.0
        result = await server.call_tool("web_search", {"query": "evidence"})
        assert result.is_error is False

    asyncio.run(exercise())
    assert core.calls == 61


def test_status_does_not_consume_rate_limit() -> None:
    core = SuccessfulCore()
    server = _server(core)

    async def exercise() -> None:
        for _ in range(75):
            await server.call_tool("web_research_status", {})
        for _ in range(60):
            await server.call_tool("web_search", {"query": "evidence"})
        with pytest.raises(ToolError) as raised:
            await server.call_tool("web_search", {"query": "evidence"})
        assert _tool_error_payload(raised.value)["code"] == "RATE_LIMITED"

    asyncio.run(exercise())
    assert core.calls == 60


def test_network_tools_never_exceed_two_concurrent_calls() -> None:
    class BlockingCore(SuccessfulCore):
        def __init__(self) -> None:
            super().__init__()
            self.active = 0
            self.max_active = 0
            self.two_entered = asyncio.Event()
            self.release = asyncio.Event()

        async def _wait(self) -> None:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.active == 2:
                self.two_entered.set()
            try:
                await self.release.wait()
            finally:
                self.active -= 1

        async def search(self, query: str, **kwargs: Any) -> SearchResult:
            await self._wait()
            return await super().search(query, **kwargs)

        async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
            await self._wait()
            return await super().fetch(url, **kwargs)

        async def map(self, url: str, **kwargs: Any) -> MapResult:
            await self._wait()
            return await super().map(url, **kwargs)

    async def exercise() -> None:
        core = BlockingCore()
        server = _server(core)
        first = Client(server)
        second = Client(server)
        await first.__aenter__()
        await second.__aenter__()
        calls: list[asyncio.Task[Any]] = []
        try:
            calls = [
                asyncio.create_task(first.call_tool("web_search", {"query": "evidence"})),
                asyncio.create_task(second.call_tool("web_fetch", {"url": "https://example.com"})),
                asyncio.create_task(first.call_tool("web_map", {"url": "https://example.com"})),
                asyncio.create_task(second.call_tool("web_search", {"query": "more"})),
                asyncio.create_task(
                    first.call_tool("web_fetch", {"url": "https://example.com/more"})
                ),
            ]
            await asyncio.wait_for(core.two_entered.wait(), timeout=1)
            await asyncio.sleep(0)
            assert core.max_active == 2
            assert core.active == 2
            core.release.set()
            await asyncio.gather(*calls)
            assert core.max_active == 2
        finally:
            core.release.set()
            if calls:
                await asyncio.gather(*calls, return_exceptions=True)
            await second.__aexit__(None, None, None)
            await first.__aexit__(None, None, None)

    asyncio.run(exercise())


def test_cancelled_call_releases_concurrency_slot() -> None:
    class CancellationCore(SuccessfulCore):
        def __init__(self) -> None:
            super().__init__()
            self.entered = 0
            self.two_entered = asyncio.Event()
            self.third_entered = asyncio.Event()
            self.release = asyncio.Event()

        async def search(self, query: str, **kwargs: Any) -> SearchResult:
            self.entered += 1
            if self.entered == 2:
                self.two_entered.set()
            if self.entered == 3:
                self.third_entered.set()
            await self.release.wait()
            return await super().search(query, **kwargs)

    async def exercise() -> None:
        core = CancellationCore()
        server = _server(core)
        first = asyncio.create_task(
            server.call_tool("web_search", {"query": "first"})
        )
        second = asyncio.create_task(
            server.call_tool("web_search", {"query": "second"})
        )
        await asyncio.wait_for(core.two_entered.wait(), timeout=1)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        third = asyncio.create_task(
            server.call_tool("web_search", {"query": "third"})
        )
        await asyncio.wait_for(core.third_entered.wait(), timeout=1)
        core.release.set()
        await asyncio.gather(second, third)

    asyncio.run(exercise())


def test_sdk_schema_error_is_distinct_from_core_invalid_request_tool_error() -> None:
    server = _server(InvalidRequestCore())

    async def exercise() -> None:
        async with Client(server) as client:
            schema_error = await client.call_tool(
                "web_search", {"query": "x" * 2001}, raise_on_error=False
            )
            core_error = await client.call_tool(
                "web_search", {"query": " "}, raise_on_error=False
            )
        assert schema_error.is_error is True
        with pytest.raises(json.JSONDecodeError):
            json.loads(schema_error.content[0].text)
        assert "validation error" in schema_error.content[0].text.lower()
        assert json.loads(core_error.content[0].text) == {
            "request_id": REQUEST_ID,
            "code": "INVALID_REQUEST",
            "message": "Request is invalid.",
        }

    asyncio.run(exercise())


def test_main_exposes_only_the_stdio_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    async def fake_runner() -> None:
        calls.append(True)

    monkeypatch.setattr(server_module, "_run_stdio", fake_runner)

    assert inspect.signature(server_module.main).parameters == {}
    server_module.main()
    assert calls == [True]
    with pytest.raises(TypeError):
        server_module.main(["--transport", "streamable-http"])


def test_importing_server_does_not_construct_client_or_export_server_instance(
    project_root: Path,
) -> None:
    project = project_root / "mcp" / "web-research-mcp"
    code = """
import httpx
def forbidden(*args, **kwargs):
    raise AssertionError('import constructed an HTTP client')
httpx.AsyncClient = forbidden
import web_research.server as server
assert not hasattr(server, 'mcp')
"""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_stdio_verifier_reports_exact_contract_with_clean_stdout(project_root: Path) -> None:
    script = project_root / "mcp" / "web-research-mcp" / "scripts" / "verify_stdio.py"
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=project_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "server": "web-research",
        "tools": sorted(EXPECTED_TOOLS),
        "status": "NOT_CONFIGURED",
        "searchError": "NOT_CONFIGURED",
        "isError": True,
    }


def test_stdio_verifier_fails_clearly_without_console_script(project_root: Path) -> None:
    script = project_root / "mcp" / "web-research-mcp" / "scripts" / "verify_stdio.py"
    environment = dict(os.environ)
    environment["PATH"] = ""
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=project_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode != 0
    assert "web-research console script is not available on PATH" in (
        completed.stdout + completed.stderr
    )


def test_deleted_legacy_modules_have_no_bytecode_artifacts(project_root: Path) -> None:
    package = project_root / "mcp" / "web-research-mcp" / "src" / "web_research"
    legacy_bytecode = [
        *package.glob("__pycache__/planning.*.pyc"),
        *package.glob("__pycache__/setup_wizard.*.pyc"),
        *package.glob("__pycache__/sources.*.pyc"),
        *package.glob("providers/__pycache__/openai_compatible.*.pyc"),
    ]
    assert legacy_bytecode == []
