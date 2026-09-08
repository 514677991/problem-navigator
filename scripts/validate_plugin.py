"""Validate this project's public Plugin contract using only the standard library.

This is a project-owned structural check, not an official Codex validator or an
installation check. It never executes commands declared by a Plugin.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _local_path(base: Path, value: Any, label: str) -> Path:
    value = _text(value, label)
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if "\\" in value or posix.is_absolute() or windows.drive or ".." in posix.parts:
        raise ValueError(f"{label} must be a portable relative path without parent traversal")
    target = (base / value).resolve()
    root = base.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"{label} escapes its containing directory")
    if not target.exists():
        raise ValueError(f"{label} target is missing")
    return target


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _release(plugin: Path) -> dict[str, Any]:
    release = _object(_json(plugin / "release.json"), {"name", "version", "license", "description"}, "project release metadata")
    for field, pattern in (("name", NAME), ("version", VERSION)):
        if not pattern.fullmatch(_text(release[field], field)):
            raise ValueError(f"release {field} has an invalid format")
    if release["license"] != "MIT":
        raise ValueError("release license must be MIT")
    _text(release["description"], "release description")
    return release


def validate_core(plugin: Path) -> dict[str, Any]:
    plugin = plugin.resolve()
    release = _release(plugin)
    for relative in ("README.md", "README.zh-CN.md", "HOST_INSTRUCTIONS.md", "LICENSE", "NOTICE.md",
                     "mcp/web-research-mcp/pyproject.toml", "mcp/web-research-mcp/uv.lock",
                     "mcp/web-research-mcp/src/web_research/server.py"):
        if not _local_path(plugin, relative, relative).is_file():
            raise ValueError(f"required file is missing: {relative}")
    if not list((plugin / "skills").glob("*/SKILL.md")):
        raise ValueError("distribution must contain skills")
    for path in plugin.rglob("*"):
        if plugin not in path.resolve().parents:
            raise ValueError("distribution path escapes its root")
        if path.name == ".mcp.json":
            raise ValueError("obsolete standalone MCP registration is not allowed")
    return release


def validate_plugin(plugin: Path, marketplace: Path | None = None) -> dict[str, Any]:
    plugin = plugin.resolve()
    manifest = _object(_json(plugin / ".codex-plugin/plugin.json"), {
        "name", "version", "description", "author", "skills", "interface", "mcpServers",
    }, "manifest")
    release = validate_core(plugin)
    if any(manifest[key] != release[key] for key in ("name", "version")):
        raise ValueError("Codex manifest identity differs from project release metadata")
    for field, pattern in (("name", NAME), ("version", VERSION)):
        if not pattern.fullmatch(_text(manifest[field], field)):
            raise ValueError(f"manifest {field} has an invalid format")
    _text(manifest["description"], "description")
    author = _object(manifest["author"], {"name"}, "author")
    _text(author["name"], "author.name")
    interface = _object(manifest["interface"], {
        "displayName", "shortDescription", "longDescription", "developerName",
        "category", "capabilities", "defaultPrompt",
    }, "interface")
    for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        _text(interface[field], f"interface.{field}")
    capabilities = interface["capabilities"]
    if (not isinstance(capabilities, list) or len(capabilities) != 3
            or not all(isinstance(value, str) for value in capabilities)
            or set(capabilities) != {"Interactive", "Research", "Write"}):
        raise ValueError("interface.capabilities must declare Interactive, Research, and Write")
    prompts = interface["defaultPrompt"]
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3:
        raise ValueError("interface.defaultPrompt must have one to three prompts")
    for prompt in prompts:
        _text(prompt, "defaultPrompt entry")

    skills = _local_path(plugin, manifest["skills"], "skills")
    if not skills.is_dir() or not list(skills.glob("*/SKILL.md")):
        raise ValueError("skills must reference a directory containing skill manifests")
    servers = _object(manifest["mcpServers"], {"web-research"}, "inline mcpServers")
    entry = _object(servers["web-research"], {"type", "command", "args", "cwd"}, "web-research")
    if entry["type"] != "stdio" or entry["command"] != "uv":
        raise ValueError("web-research must use the local uv stdio command")
    args = entry["args"]
    if (not isinstance(args, list) or len(args) != 6
            or args[:4] != ["run", "--locked", "--isolated", "--project"]
            or args[-1] != "web-research"):
        raise ValueError("web-research must launch uv run --locked --isolated --project PATH web-research")
    cwd = _local_path(plugin, entry["cwd"], "MCP cwd")
    if not cwd.is_dir():
        raise ValueError("MCP cwd must be a directory")
    project = _local_path(cwd, args[4], "MCP project")
    for relative in ("pyproject.toml", "uv.lock", "src/web_research/server.py"):
        if not (project / relative).is_file():
            raise ValueError(f"MCP project is missing {relative}")

    for path in plugin.rglob("*"):
        resolved = path.resolve()
        if plugin not in resolved.parents:
            raise ValueError("Plugin contains a path that escapes its root")

    if marketplace is None:
        marketplace = plugin / ".agents/plugins/marketplace.json"
    if marketplace is not None:
        marketplace = marketplace.resolve()
        if marketplace.parts[-3:] != (".agents", "plugins", "marketplace.json"):
            raise ValueError("marketplace must be located at .agents/plugins/marketplace.json")
        catalog = _object(_json(marketplace), {"name", "interface", "plugins"}, "marketplace")
        _text(catalog["name"], "marketplace.name")
        display = _object(catalog["interface"], {"displayName"}, "marketplace.interface")
        _text(display["displayName"], "marketplace displayName")
        if not isinstance(catalog["plugins"], list) or len(catalog["plugins"]) != 1:
            raise ValueError("marketplace must contain exactly this Plugin")
        listing = _object(catalog["plugins"][0], {"name", "source", "policy", "category"}, "marketplace Plugin")
        if listing["name"] != manifest["name"] or listing["category"] != interface["category"]:
            raise ValueError("marketplace identity/category do not match the Plugin manifest")
        source = _object(listing["source"], {"source", "path"}, "marketplace source")
        if source["source"] != "local":
            raise ValueError("marketplace source must be local")
        if _local_path(marketplace.parents[2], source["path"], "marketplace source") != plugin:
            raise ValueError("marketplace source does not reference this Plugin")
        if listing["policy"] != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
            raise ValueError("marketplace policy must use AVAILABLE and ON_INSTALL")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", type=Path)
    parser.add_argument("--marketplace", type=Path)
    args = parser.parse_args()
    try:
        manifest = validate_plugin(args.plugin, args.marketplace)
    except (ValueError, OSError, TypeError) as error:
        print(f"Plugin validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Plugin validation passed: {manifest['name']} {manifest['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
