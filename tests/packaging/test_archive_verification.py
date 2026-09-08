from __future__ import annotations

import asyncio
import importlib.util
import json
import warnings
import sys
from types import SimpleNamespace
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _verifier():
    spec = importlib.util.spec_from_file_location(
        "archive_registration_verifier", ROOT / "tests/verify_plugin_mcp_registration.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("names", [
    ["../outside.txt"], ["/absolute.txt"], ["C:/absolute.txt"], ["C:relative.txt"],
    ["folder\\..\\outside.txt"], ["payload.txt", "payload.txt"],
    ["payload.txt", "./payload.txt"], ["symlink"], ["folder/file:stream"],
])
def test_archive_verification_rejects_unsafe_entries_before_dispatch(tmp_path, monkeypatch, names):
    module = _verifier()
    archive = tmp_path / "unsafe.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(archive, "w") as bundle:
            for name in names:
                info = ZipInfo(name)
                if name == "symlink":
                    info.create_system = 3
                    info.external_attr = 0o120777 << 16
                bundle.writestr(info, "unsafe")
    async def reject_dispatch(plugin):
        pytest.fail("An unsafe archive reached MCP dispatch")
    monkeypatch.setattr(module, "verify", reject_dispatch)
    operation = getattr(module, "verify_archive", None)
    assert callable(operation), "Archive verification must be available"
    with pytest.raises(ValueError, match="unsafe|duplicate"):
        asyncio.run(operation(archive))
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.parametrize("dispatch_fails", [False, True])
def test_archive_verification_dispatches_extracted_bytes_and_cleans_up(tmp_path, monkeypatch, dispatch_fails):
    module = _verifier()
    archive = tmp_path / "release.zip"
    payload = {".mcp.json": b'{"mcpServers": {}}', "skills/analysis/SKILL.md": b"# Analysis"}
    with ZipFile(archive, "w") as bundle:
        for name, data in payload.items():
            bundle.writestr(name, data)
    observed_roots = []
    async def inspect_extracted_plugin(plugin):
        observed_roots.append(plugin)
        assert plugin != tmp_path
        assert {p.relative_to(plugin).as_posix(): p.read_bytes()
                for p in plugin.rglob("*") if p.is_file()} == payload
        if dispatch_fails:
            raise RuntimeError("MCP verification failed")
    monkeypatch.setattr(module, "verify", inspect_extracted_plugin)
    operation = getattr(module, "verify_archive", None)
    assert callable(operation), "Archive verification must be available"
    if dispatch_fails:
        with pytest.raises(RuntimeError, match="MCP verification failed"):
            asyncio.run(operation(archive))
    else:
        asyncio.run(operation(archive))
    assert len(observed_roots) == 1
    assert not observed_roots[0].exists()
    assert archive.is_file()


@pytest.mark.parametrize("explicit_uv_settings", [False, True])
def test_verification_environment_retains_cache_and_interpreter_while_isolating_provider_config(
    tmp_path, monkeypatch, explicit_uv_settings
):
    module = _verifier()
    monkeypatch.setenv("BRAVE_API_KEY", "synthetic-secret")
    monkeypatch.setenv("UV_LINK_MODE", "copy")
    for name in ("UV_CACHE_DIR", "UV_PYTHON"):
        monkeypatch.delenv(name, raising=False)
    if explicit_uv_settings:
        monkeypatch.setenv("UV_CACHE_DIR", "/selected/cache")
        monkeypatch.setenv("UV_PYTHON", "3.11")
    def cache_dir(command, **kwargs):
        assert not explicit_uv_settings, "Explicit cache settings must not be queried again"
        assert command == ["uv", "cache", "dir"]
        return SimpleNamespace(stdout="/existing/cache\n")
    monkeypatch.setattr(module, "subprocess", SimpleNamespace(run=cache_dir), raising=False)
    operation = getattr(module, "verification_environment", None)
    assert callable(operation), "Verification must preserve uv state before isolating HOME"
    environment = operation("uv", str(tmp_path))
    assert environment["UV_CACHE_DIR"] == ("/selected/cache" if explicit_uv_settings else "/existing/cache")
    assert environment["UV_PYTHON"] == ("3.11" if explicit_uv_settings else sys.executable)
    assert environment["HOME"] == environment["USERPROFILE"] == str(tmp_path)
    assert not set(module.KEYS).intersection(environment)
    assert environment["UV_LINK_MODE"] == "copy"
    assert environment["UV_OFFLINE"] == "1"


def test_verification_forces_offline_when_parent_explicitly_allows_downloads(tmp_path, monkeypatch):
    module = _verifier()
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("UV_OFFLINE", "0")
    environment = module.verification_environment("uv", str(tmp_path / "home"))
    assert environment["UV_OFFLINE"] == "1"


@pytest.mark.parametrize("verification_fails", [False, True])
@pytest.mark.parametrize("mode", ["declared", "direct"])
def test_one_shot_verification_closes_real_stdio_before_releasing_its_directory(
    tmp_path, monkeypatch, verification_fails, mode
):
    module = _verifier()
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    registration = plugin / ".codex-plugin/plugin.json"
    registration.parent.mkdir()
    registration.write_text(json.dumps({"mcpServers": {"web-research": {
        "command": sys.executable,
        "args": ["-c", "from web_research.server import main; main()"],
        "cwd": ".",
    }}}), encoding="utf-8")
    if mode == "direct":
        registration.unlink()
        registration.parent.rmdir()
        (plugin / "mcp/web-research-mcp").mkdir(parents=True)
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "unused-cache"))
    real_transport = module.StdioTransport
    transports = []
    def observe_transport(**kwargs):
        if mode == "direct":
            assert kwargs["command"] == "uv"
            assert kwargs["args"] == ["run", "--locked", "--isolated", "--project",
                                      str((plugin / "mcp/web-research-mcp").resolve()), "web-research"]
            # Exercise real MCP lifecycle without testing uv's package resolver here.
            kwargs.update(command=sys.executable, args=["-c", "from web_research.server import main; main()"])
        transport = real_transport(**kwargs)
        transports.append(transport)
        return transport
    monkeypatch.setattr(module, "StdioTransport", observe_transport)
    if verification_fails:
        monkeypatch.setattr(module, "EXPECTED_TOOLS", {"deliberately_missing_tool"})

    async def exercise():
        try:
            if verification_fails:
                with pytest.raises(SystemExit):
                    await module.verify(plugin, mode=mode)
            else:
                await module.verify(plugin, mode=mode)
            # FastMCP keeps subprocesses alive by default after Client.__aexit__.
            # Our one-shot verifier must await that real background task's exit.
            connection = transports[0]._connect_task
            assert connection is None or connection.done(), "stdio subprocess is still running"
            if mode == "declared":
                registration.unlink()
                registration.parent.rmdir()
            else:
                (plugin / "mcp/web-research-mcp").rmdir()
                (plugin / "mcp").rmdir()
            plugin.rmdir()  # Windows refuses this while the subprocess holds cwd.
        finally:
            for transport in transports:
                await transport.close()
    asyncio.run(exercise())
