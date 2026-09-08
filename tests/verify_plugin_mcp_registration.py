"""Verify a Plugin's declared local stdio MCP registration without changing it."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


EXPECTED_TOOLS = {"web_research_status", "web_search", "web_fetch", "web_map"}
KEYS = ("BRAVE_API_KEY", "EXA_API_KEY", "FIRECRAWL_API_KEY")


def verification_environment(command: str, temporary_home: str) -> dict[str, str]:
    child_env = dict(os.environ)
    if not child_env.get("UV_CACHE_DIR"):
        cache = subprocess.run(
            [command, "cache", "dir"], check=True, capture_output=True, text=True
        ).stdout.strip()
        if not cache:
            raise ValueError("uv cache dir returned an empty path")
        child_env["UV_CACHE_DIR"] = cache
    child_env.setdefault("UV_PYTHON", sys.executable)
    for key in KEYS:
        child_env.pop(key, None)
    child_env["HOME"] = temporary_home
    child_env["USERPROFILE"] = temporary_home
    child_env["UV_OFFLINE"] = "1"
    return child_env


async def verify_archive(archive: Path, mode: str = "declared") -> None:
    """Check portable ZIP paths before extracting; never write into the mirror."""
    with TemporaryDirectory(prefix="web-research-archive-") as temporary:
        plugin = Path(temporary)
        with ZipFile(archive) as bundle:
            seen: set[str] = set()
            for entry in bundle.infolist():
                path = PurePosixPath(entry.filename)
                windows = PureWindowsPath(entry.filename)
                if (not path.parts or path.is_absolute() or windows.drive
                        or "\\" in entry.filename or ":" in entry.filename
                        or ".." in path.parts or windows.is_reserved()
                        or any(part.endswith((".", " ")) for part in path.parts)
                        or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError("unsafe archive entry")
                normalized = path.as_posix().casefold()
                if normalized in seen:
                    raise ValueError("duplicate archive entry")
                seen.add(normalized)
            bundle.extractall(plugin)
        if mode == "declared":
            await verify(plugin)
        else:
            await verify(plugin, mode=mode)


async def verify(plugin: Path, mode: str = "declared") -> None:
    plugin = plugin.resolve()
    if mode == "direct":
        project = (plugin / "mcp/web-research-mcp").resolve()
        if plugin not in project.parents or not project.is_dir():
            raise SystemExit("Generic MCP project is missing or escapes distribution root")
        registration = {"mcpServers": {"web-research": {
            "command": "uv", "args": ["run", "--locked", "--isolated", "--project", str(project), "web-research"],
            "cwd": ".",
        }}}
    elif mode == "declared":
        manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        registration = {"mcpServers": manifest.get("mcpServers")}
    else:
        raise ValueError("unknown access mode")
    servers = registration.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != {"web-research"}:
        raise SystemExit("Plugin must declare exactly mcpServers.web-research")
    entry = servers["web-research"]
    if not isinstance(entry, dict) or not isinstance(entry.get("command"), str):
        raise SystemExit("web-research registration has no executable command")
    if not isinstance(entry.get("args"), list) or not all(isinstance(arg, str) for arg in entry["args"]):
        raise SystemExit("web-research registration has invalid args")
    cwd = (plugin / entry.get("cwd", ".")).resolve()
    if plugin not in cwd.parents and cwd != plugin:
        raise SystemExit("web-research registration cwd escapes Plugin root")

    with TemporaryDirectory(prefix="web-research-verify-") as temporary_home:
        child_env = verification_environment(entry["command"], temporary_home)
        transport = StdioTransport(
            command=entry["command"], args=entry["args"], cwd=str(cwd), env=child_env,
            keep_alive=False,  # Release the subprocess cwd before temporary directory cleanup.
        )
        async with Client(transport) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            if set(tools) != EXPECTED_TOOLS:
                raise SystemExit(json.dumps({"tools": sorted(tools)}, ensure_ascii=False))
            for tool in tools.values():
                if tool.input_schema.get("additionalProperties") is not False:
                    raise SystemExit(f"tool schema is not strict: {tool.name}")
            status = await client.call_tool("web_research_status", {}, raise_on_error=False)
            search = await client.call_tool(
                "web_search", {"query": "offline configuration check"}, raise_on_error=False
            )
    if status.is_error or status.structured_content is None:
        raise SystemExit("status was not callable")
    if not search.is_error:
        raise SystemExit("unconfigured search was not a safe ToolError")
    error = json.loads(search.content[0].text)
    if error.get("code") != "NOT_CONFIGURED":
        raise SystemExit("unconfigured search did not return NOT_CONFIGURED")
    print(json.dumps({"registration": "valid", "tools": sorted(tools), "status": "NOT_CONFIGURED"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--plugin-root", type=Path)
    source.add_argument("--archive", type=Path)
    parser.add_argument("--mode", choices=("direct", "declared"), default="declared")
    args = parser.parse_args()
    asyncio.run(verify_archive(args.archive, args.mode) if args.archive else verify(args.plugin_root, args.mode))
