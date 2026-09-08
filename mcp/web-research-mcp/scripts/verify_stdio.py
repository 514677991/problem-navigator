"""Verify the installed four-tool server over its only transport: stdio."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from tempfile import TemporaryDirectory

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


EXPECTED_TOOLS = {
    "web_research_status",
    "web_search",
    "web_fetch",
    "web_map",
}
PROVIDER_KEYS = {"BRAVE_API_KEY", "EXA_API_KEY", "FIRECRAWL_API_KEY"}


async def verify() -> dict[str, object]:
    command = shutil.which("web-research")
    if command is None:
        raise SystemExit("web-research console script is not available on PATH")
    with TemporaryDirectory(prefix="web-research-verify-") as temporary_home:
        clean_env = {
            key: value for key, value in os.environ.items() if key not in PROVIDER_KEYS
        }
        clean_env["HOME"] = temporary_home
        clean_env["USERPROFILE"] = temporary_home
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        transport = StdioTransport(
            command=command,
            args=[],
            env=clean_env,
        )
        async with Client(transport) as client:
            tools = await client.list_tools()
            by_name = {tool.name: tool for tool in tools}
            if set(by_name) != EXPECTED_TOOLS:
                raise SystemExit(f"unexpected tools: {sorted(by_name)}")
            for tool in by_name.values():
                if tool.input_schema.get("additionalProperties") is not False:
                    raise SystemExit(f"{tool.name} input schema is not strict")
                if (
                    not tool.output_schema
                    or tool.output_schema.get("additionalProperties") is not False
                ):
                    raise SystemExit(f"{tool.name} output schema is not strict")

            status = await client.call_tool(
                "web_research_status", {}, raise_on_error=False
            )
            search = await client.call_tool(
                "web_search",
                {"query": "must-not-hit-network"},
                raise_on_error=False,
            )

        if status.is_error or status.structured_content is None:
            raise SystemExit("status did not return a successful structured result")
        config_state = status.structured_content.get("config_state")
        if config_state != "NOT_CONFIGURED":
            raise SystemExit(f"unexpected status: {config_state}")
        if not search.is_error or search.structured_content is not None:
            raise SystemExit("unconfigured search did not return a text-only MCP error")
        if len(search.content) != 1:
            raise SystemExit("unconfigured search did not return exactly one content block")
        payload = json.loads(search.content[0].text)
        if set(payload) != {"request_id", "code", "message"}:
            raise SystemExit("unconfigured search returned an invalid error shape")
        if payload["code"] != "NOT_CONFIGURED":
            raise SystemExit("unconfigured search returned the wrong error code")

        return {
            "server": "web-research",
            "tools": sorted(by_name),
            "status": config_state,
            "searchError": payload["code"],
            "isError": search.is_error,
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(verify()), ensure_ascii=False, separators=(",", ":")))
