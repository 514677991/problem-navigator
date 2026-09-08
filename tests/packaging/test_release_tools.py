from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validate_plugin.py"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def release_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "public-project"
    plugin = root / "plugins" / "example-analysis"
    source_plugin = ROOT / "adapters/codex"
    manifest = json.loads((source_plugin / ".codex-plugin/plugin.json").read_text("utf-8"))
    manifest.update(name="example-analysis", version="4.5.6")
    _write_json(plugin / ".codex-plugin/plugin.json", manifest)
    _write_json(root / ".agents/plugins/marketplace.json", {
        "name": "public-project", "interface": {"displayName": "Public Project"},
        "plugins": [{"name": "example-analysis", "source": {
            "source": "local", "path": "./plugins/example-analysis"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity"}],
    })
    for base in (root, plugin):
        for relative, text in {
            "skills/analysis/SKILL.md": "---\nname: analysis\ndescription: Analyze a problem.\n---\n",
            "mcp/web-research-mcp/pyproject.toml": '[project]\nname = "web-research-mcp"\n',
            "mcp/web-research-mcp/uv.lock": "version = 1\n",
            "mcp/web-research-mcp/src/web_research/server.py": "def main(): pass\n",
            "LICENSE": "MIT License\nFixture contributors\n",
            "NOTICE.md": "Third-party dependencies retain their own licenses.\n",
        }.items():
            path = base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for name in ("README.md", "README.zh-CN.md"):
        (plugin / name).write_text(f"# {name}\n", encoding="utf-8")
    _write_json(root / "release.json", {"name": "example-analysis", "version": "4.5.6",
                "license": "MIT", "description": "A portable analysis plugin."})
    shutil.copy2(root / "release.json", plugin / "release.json")
    adapter = root / "adapters/codex"
    shutil.copytree(plugin, adapter)
    shutil.rmtree(adapter / "mcp")
    shutil.rmtree(adapter / "skills")
    ui = adapter / "skills/analysis/agents/openai.yaml"
    ui.parent.mkdir(parents=True)
    ui.write_text("policy:\n  allow_implicit_invocation: true\n", encoding="utf-8")
    generic = root / "adapters/generic"
    generic.mkdir(parents=True)
    for name in ("README.md", "README.zh-CN.md", "HOST_INSTRUCTIONS.md"):
        (generic / name).write_text("# Portable plugin\n", encoding="utf-8")
        shutil.copy2(generic / name, plugin / name)
    for name in ("README.md", "README.zh-CN.md"):
        destination = plugin / "adapters/codex" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(adapter / name, destination)
    catalog = json.loads((root / ".agents/plugins/marketplace.json").read_text("utf-8"))
    catalog["plugins"][0]["source"]["path"] = "."
    _write_json(plugin / ".agents/plugins/marketplace.json", catalog)
    return root, plugin


def _validate(root: Path, plugin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([
        sys.executable, str(VALIDATOR), str(plugin), "--marketplace",
        str(root / ".agents/plugins/marketplace.json"),
    ], capture_output=True, text=True, check=False)


def test_project_validator_accepts_a_relocated_plugin_without_installed_codex_files(release_project):
    result = _validate(*release_project)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("mutation", [
    "missing_name", "unexpected_manifest_key", "invalid_version", "empty_description",
    "wrong_capabilities_type", "missing_capability", "unknown_interface_key",
    "skills_escape", "windows_absolute_path", "external_registration", "cwd_escape",
    "unlocked_command", "project_escape", "registration_environment",
    "marketplace_name_mismatch", "marketplace_path_escape", "marketplace_wrong_target",
])
def test_project_validator_rejects_invalid_contracts(release_project, mutation):
    root, plugin = release_project
    manifest_path = plugin / ".codex-plugin/plugin.json"
    marketplace_path = root / ".agents/plugins/marketplace.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    marketplace = json.loads(marketplace_path.read_text("utf-8"))
    entry = manifest["mcpServers"]["web-research"]
    if mutation == "missing_name": del manifest["name"]
    elif mutation == "unexpected_manifest_key": manifest["install"] = "custom-command"
    elif mutation == "invalid_version": manifest["version"] = "../../escape"
    elif mutation == "empty_description": manifest["description"] = " "
    elif mutation == "wrong_capabilities_type": manifest["interface"]["capabilities"] = "Research"
    elif mutation == "missing_capability": manifest["interface"]["capabilities"] = ["Research"]
    elif mutation == "unknown_interface_key": manifest["interface"]["unknown"] = True
    elif mutation == "skills_escape": manifest["skills"] = "../../skills"
    elif mutation == "windows_absolute_path": manifest["skills"] = "C:\\private\\skills"
    elif mutation == "external_registration": manifest["mcpServers"] = "./missing.json"
    elif mutation == "cwd_escape": entry["cwd"] = "../.."
    elif mutation == "unlocked_command": entry["args"].remove("--locked")
    elif mutation == "project_escape": entry["args"][4] = "../../outside"
    elif mutation == "registration_environment": entry["env"] = {"EXA_API_KEY": "unsafe"}
    elif mutation == "marketplace_name_mismatch": marketplace["plugins"][0]["name"] = "other-plugin"
    elif mutation == "marketplace_path_escape": marketplace["plugins"][0]["source"]["path"] = "../outside"
    elif mutation == "marketplace_wrong_target": marketplace["plugins"][0]["source"]["path"] = "./skills"
    _write_json(manifest_path, manifest)
    _write_json(marketplace_path, marketplace)
    result = _validate(root, plugin)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "validation failed" in result.stderr.lower()


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_uses_manifest_identity_and_includes_bilingual_and_legal_files(release_project, monkeypatch):
    root, plugin = release_project
    builder = _load_script("build_plugin_zip")
    for name, value in {"ROOT": root, "PLUGIN": plugin, "CANONICAL_SKILLS": root / "skills",
                        "CANONICAL_MCP": root / "mcp/web-research-mcp"}.items():
        monkeypatch.setattr(builder, name, value)
    builder.main()
    target = root / "dist/example-analysis-4.5.6.zip"
    assert target.is_file(), "The release filename must follow the manifest identity"
    with zipfile.ZipFile(target) as bundle:
        assert {"README.md", "README.zh-CN.md", "LICENSE", "NOTICE.md"} <= set(bundle.namelist())
        assert bundle.read("LICENSE") == (root / "LICENSE").read_bytes()
        assert bundle.read("NOTICE.md") == (root / "NOTICE.md").read_bytes()
    checksum = target.with_suffix(".zip.sha256").read_text("utf-8")
    assert checksum == f"{hashlib.sha256(target.read_bytes()).hexdigest()}  {target.name}\n"


def test_release_bytes_are_independent_of_source_mtime(release_project, monkeypatch):
    root, plugin = release_project
    builder = _load_script("build_plugin_zip")
    for name, value in {"ROOT": root, "PLUGIN": plugin, "CANONICAL_SKILLS": root / "skills",
                        "CANONICAL_MCP": root / "mcp/web-research-mcp"}.items():
        monkeypatch.setattr(builder, name, value)
    builder.main()
    target = next((root / "dist").glob("*.zip"))
    first = target.read_bytes()
    for source in list((root / "skills").rglob("*")) + list(plugin.rglob("*")):
        if source.is_file(): os.utime(source, (946684800, 946684800))
    builder.main()
    assert target.read_bytes() == first
    with zipfile.ZipFile(target) as bundle:
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in bundle.infolist())
        assert all(info.create_system == 3 and info.external_attr >> 16 == 0o100644
                   for info in bundle.infolist())


def test_sync_copies_and_checks_root_legal_documents(release_project, monkeypatch):
    root, plugin = release_project
    sync = _load_script("sync_plugin_payload")
    for name, value in {"ROOT": root, "PLUGIN_ROOT": plugin, "CANONICAL_SKILLS": root / "skills",
                        "CANONICAL_MCP": root / "mcp/web-research-mcp"}.items():
        monkeypatch.setattr(sync, name, value)
    (plugin / "LICENSE").write_text("stale license", encoding="utf-8")
    (plugin / "NOTICE.md").unlink()
    assert sync.check() == 1
    assert sync.write() == 0
    assert (plugin / "LICENSE").read_bytes() == (root / "LICENSE").read_bytes()
    assert (plugin / "NOTICE.md").read_bytes() == (root / "NOTICE.md").read_bytes()


def test_single_release_has_inline_adapter_and_self_referencing_marketplace(release_project, monkeypatch):
    root, plugin = release_project
    builder = _load_script("build_plugin_zip")
    for name, value in {"ROOT": root, "PLUGIN": plugin, "CANONICAL_SKILLS": root / "skills",
                        "CANONICAL_MCP": root / "mcp/web-research-mcp"}.items():
        monkeypatch.setattr(builder, name, value)
    builder.main()
    archives = list((root / "dist").glob("*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as bundle:
        names = bundle.namelist()
        assert ".codex-plugin/plugin.json" in names
        manifest = json.loads(bundle.read(".codex-plugin/plugin.json"))
        assert isinstance(manifest["mcpServers"], dict)
        assert not any(name.endswith(".mcp.json") for name in names)
        catalog = json.loads(bundle.read(".agents/plugins/marketplace.json"))
        assert catalog["plugins"][0]["source"]["path"] == "."
        assert {"HOST_INSTRUCTIONS.md", "adapters/codex/README.md", "skills/analysis/agents/openai.yaml"} <= set(names)
        assert len([name for name in names if name.endswith("server.py")]) == 1
        extracted = root.parent / "extracted-release"
        bundle.extractall(extracted)
    validation = subprocess.run([sys.executable, str(VALIDATOR), str(extracted)],
                                capture_output=True, text=True, check=False)
    assert validation.returncode == 0, validation.stdout + validation.stderr
    source_catalog = json.loads((root / ".agents/plugins/marketplace.json").read_text("utf-8"))
    assert source_catalog["plugins"][0]["source"]["path"] == "./plugins/example-analysis"


def test_sync_removes_obsolete_root_registration_after_metadata_commit(release_project, monkeypatch):
    root, plugin = release_project
    sync = _load_script("sync_plugin_payload")
    for name, value in {"ROOT": root, "PLUGIN_ROOT": plugin, "CANONICAL_SKILLS": root / "skills",
                        "CANONICAL_MCP": root / "mcp/web-research-mcp"}.items():
        monkeypatch.setattr(sync, name, value)
    (plugin / ".mcp.json").write_text("{}", encoding="utf-8")
    assert sync.write() == 0
    assert not (plugin / ".mcp.json").exists()
    (plugin / ".mcp.json").write_text("{}", encoding="utf-8")
    assert sync.check() == 1


def test_obsolete_registration_cleanup_unlinks_named_entry_not_resolved_target(release_project, monkeypatch):
    root, plugin = release_project
    sync = _load_script("sync_plugin_payload")
    for name, value in {"ROOT": root, "PLUGIN_ROOT": plugin, "CANONICAL_SKILLS": root / "skills",
                        "CANONICAL_MCP": root / "mcp/web-research-mcp"}.items():
        monkeypatch.setattr(sync, name, value)
    obsolete = plugin / ".mcp.json"
    obsolete.write_text("old registration", encoding="utf-8")
    survivor = plugin / "survivor.txt"
    survivor.write_text("preserve this file", encoding="utf-8")
    real_guard = sync._strict_child
    def resolve_registration_alias(path, parent):
        # Model a contained symlink resolution without Windows symlink privileges.
        return survivor.resolve() if path == obsolete else real_guard(path, parent)
    monkeypatch.setattr(sync, "_strict_child", resolve_registration_alias)
    sync.write()
    assert survivor.is_file(), "cleanup followed the resolved target instead of unlinking .mcp.json"
    assert not obsolete.exists()
