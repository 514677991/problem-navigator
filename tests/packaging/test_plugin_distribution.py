from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SKILLS = ROOT / "skills"
CANONICAL_MCP = ROOT / "mcp" / "web-research-mcp"
PLUGIN = ROOT / "plugins" / "problem-navigator"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_payload() -> dict[str, Path]:
    payload = {
        ".codex-plugin/plugin.json": PLUGIN / ".codex-plugin" / "plugin.json",
        ".agents/plugins/marketplace.json": PLUGIN / ".agents/plugins/marketplace.json",
        "README.md": ROOT / "adapters/generic/README.md",
        "README.zh-CN.md": ROOT / "adapters/generic/README.zh-CN.md",
        "HOST_INSTRUCTIONS.md": ROOT / "adapters/generic/HOST_INSTRUCTIONS.md",
        "adapters/codex/README.md": ROOT / "adapters/codex/README.md",
        "adapters/codex/README.zh-CN.md": ROOT / "adapters/codex/README.zh-CN.md",
        "release.json": ROOT / "release.json",
        "LICENSE": ROOT / "LICENSE",
        "NOTICE.md": ROOT / "NOTICE.md",
    }
    for source in sorted(CANONICAL_SKILLS.rglob("*")):
        if source.is_file() and "__pycache__" not in source.parts and source.suffix not in {".pyc", ".pyo"}:
            payload[(Path("skills") / source.relative_to(CANONICAL_SKILLS)).as_posix()] = source
    for name in ("pyproject.toml", "uv.lock"):
        payload[f"mcp/web-research-mcp/{name}"] = CANONICAL_MCP / name
    for source in sorted((CANONICAL_MCP / "src").rglob("*.py")):
        payload[(Path("mcp/web-research-mcp/src") / source.relative_to(CANONICAL_MCP / "src")).as_posix()] = source
    adapter = ROOT / "adapters/codex"
    for source in sorted((adapter / "skills").glob("*/agents/openai.yaml")):
        payload[source.relative_to(adapter).as_posix()] = source
    return payload


def _load_build_module():
    script = ROOT / "scripts" / "build_plugin_zip.py"
    spec = importlib.util.spec_from_file_location("plugin_zip_builder", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_sync_module():
    script = ROOT / "scripts" / "sync_plugin_payload.py"
    spec = importlib.util.spec_from_file_location("plugin_payload_sync", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_skill_runtime_cache_is_excluded_from_sync_and_archive(tmp_path, monkeypatch):
    skill = tmp_path / "skills" / "problem-navigator" / "scripts"
    cache = skill / "__pycache__"
    cache.mkdir(parents=True)
    (skill / "workflow_control.py").write_text("# production control", encoding="utf-8")
    (cache / "workflow_control.cpython-312.pyc").write_bytes(b"runtime-cache")
    for module in (_load_sync_module(), _load_build_module()):
        monkeypatch.setattr(module, "CANONICAL_SKILLS", tmp_path / "skills")
        payload = module._canonical_skills() if hasattr(module, "_canonical_skills") else module.production_payload()
        assert any(name.endswith("workflow_control.py") for name in payload)
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in payload)


def test_manifest_and_mcp_registration_are_the_v2_distribution_contract() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text("utf-8"))
    adapter = json.loads((ROOT / "adapters/codex/.codex-plugin/plugin.json").read_text("utf-8"))
    release = json.loads((ROOT / "release.json").read_text("utf-8"))
    assert manifest == {**adapter, "name": release["name"], "version": release["version"]}
    assert manifest["name"] == "problem-navigator"
    assert manifest["skills"] == "./skills/"
    assert isinstance(manifest["mcpServers"], dict)
    assert set(manifest["interface"]["capabilities"]) == {"Interactive", "Research", "Write"}
    assert len(manifest["interface"]["defaultPrompt"]) <= 3
    assert not (PLUGIN / ".mcp.json").exists()
    registration = {"mcpServers": manifest["mcpServers"]}
    assert registration == {
        "mcpServers": {
            "web-research": {
                "type": "stdio",
                "command": "uv",
                "args": [
                    "run", "--locked", "--isolated", "--project",
                    "./mcp/web-research-mcp", "web-research",
                ],
                "cwd": ".",
            }
        }
    }


def test_canonical_production_payload_is_exactly_mirrored_without_development_files() -> None:
    canonical = _canonical_payload()
    mirrored = {
        path.relative_to(PLUGIN).as_posix(): path
        for path in PLUGIN.rglob("*")
        if path.is_file()
    }
    assert set(mirrored) == set(canonical)
    assert {name: _sha256(path) for name, path in mirrored.items()} == {
        name: _sha256(path) for name, path in canonical.items()
    }
    forbidden = {"tests", "scripts", "README.md", "VERIFICATION.md", "build", "__pycache__"}
    for path in (PLUGIN / "mcp" / "web-research-mcp").rglob("*"):
        assert not any(part in forbidden or part.endswith(".egg-info") for part in path.parts)
    assert not (PLUGIN / "skills" / "web-research-execution").exists()


def test_shared_references_are_nested_under_the_entry_skill_and_all_links_resolve() -> None:
    assert not (CANONICAL_SKILLS / "_shared").exists()
    skill_manifests = sorted(CANONICAL_SKILLS.rglob("SKILL.md"))
    assert len(skill_manifests) == 9

    references = CANONICAL_SKILLS / "problem-navigator" / "references"
    expected_references = {
        "artifacts.schema.json",
        "evidence-package-validation.md",
        "workflow-control.md",
    }
    assert {path.name for path in references.iterdir() if path.is_file()} == expected_references

    expected_links = {
        "problem-navigator": ("references/artifacts.schema.json",),
        "problem-framing": (
            "../problem-navigator/references/artifacts.schema.json",
        ),
        "research-design-kickoff": (
            "../problem-navigator/references/artifacts.schema.json",
        ),
        "research-execution": (
            "../problem-navigator/references/artifacts.schema.json",
            "../problem-navigator/references/evidence-package-validation.md",
        ),
        "decision-readiness-interview": (
            "../problem-navigator/references/evidence-package-validation.md",
        ),
        "adversarial-option-selection": (
            "../problem-navigator/references/evidence-package-validation.md",
        ),
        "solution-refinement": (
            "../problem-navigator/references/artifacts.schema.json",
        ),
        "solution-decomposition": (
            "../problem-navigator/references/artifacts.schema.json",
        ),
    }
    for skill_name, relative_links in expected_links.items():
        skill_root = CANONICAL_SKILLS / skill_name
        contents = (skill_root / "SKILL.md").read_text("utf-8")
        for relative_link in relative_links:
            assert relative_link in contents
            assert (skill_root / relative_link).resolve().is_file()


def test_built_zip_has_only_the_independently_expected_distribution_payload() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_plugin_zip.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text("utf-8"))
    target = ROOT / "dist" / f"{manifest['name']}-{manifest['version']}.zip"
    assert target.is_file()
    with zipfile.ZipFile(target) as bundle:
        names = bundle.namelist()
        assert len(names) == len(set(names))
        assert all("\\" not in name and ".." not in Path(name).parts for name in names)
        assert set(names) == set(_canonical_payload())
        for name, source in _canonical_payload().items():
            assert hashlib.sha256(bundle.read(name)).hexdigest() == _sha256(source)
        assert "skills/problem-navigator/references/artifacts.schema.json" in names
        assert (
            "skills/problem-navigator/references/evidence-package-validation.md"
            in names
        )
        assert not any("_shared" in Path(name).parts for name in names)
    forbidden_markers = (
        b"openai_compatible", b"web-research-execution", b"plan_intent",
    )
    with zipfile.ZipFile(target) as bundle:
        payload = b"\n".join(bundle.read(name) for name in bundle.namelist())
    assert not any(marker.lower() in payload.lower() for marker in forbidden_markers)
    assert not any(".problem-navigator" in name or name.endswith("web-research.json") for name in names)


def test_secret_scanner_rejects_actual_and_hard_coded_keys_but_allows_documentation_placeholders(
    tmp_path: Path,
) -> None:
    module = _load_build_module()
    staging = tmp_path / "staging"
    staging.mkdir()
    safe = staging / "README.md"
    safe.write_text('BRAVE_API_KEY="..." EXA_API_KEY=<YOUR_API_KEY> ${FIRECRAWL_API_KEY}', encoding="utf-8")
    module.scan_staging(staging, {"BRAVE_API_KEY": "actual-secret-value-1234"})
    safe.write_text("the actual-secret-value-1234", encoding="utf-8")
    with pytest.raises(ValueError, match="environment secret"):
        module.scan_staging(staging, {"BRAVE_API_KEY": "actual-secret-value-1234"})
    safe.write_text("EXA_API_KEY=abcdefghijklmnop", encoding="utf-8")
    with pytest.raises(ValueError, match="hard-coded provider credential"):
        module.scan_staging(staging, {})


@pytest.mark.parametrize(
    "contents",
    [
        '"EXA_API_KEY": "abcdefghijklmnop"',
        "'FIRECRAWL_TOKEN' = 'abc+/def_ghi-jkl.mno='",
    ],
)
def test_secret_scanner_rejects_quoted_json_and_opaque_provider_credentials(
    tmp_path: Path, contents: str
) -> None:
    module = _load_build_module()
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "payload.txt").write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="hard-coded provider credential"):
        module.scan_staging(staging, {})


@pytest.mark.parametrize(
    "relative",
    [
        "web-research.json",
        "settings/web-research.local.json",
        "workflow.yaml",
        "cache.db",
        ".pytest_cache/state",
        "test_helper.py",
        ".env.production",
        "build/generated.py",
        "src/__pycache__/module.pyc",
        "src/package.egg-info/PKG-INFO",
    ],
)
def test_secret_scanner_rejects_user_configuration_and_packaging_path_variants(
    tmp_path: Path, relative: str
) -> None:
    module = _load_build_module()
    staging = tmp_path / "staging"
    target = staging / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("safe", encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden distribution path"):
        module.scan_staging(staging, {})


def test_secret_scanner_allows_static_plugin_json_and_documentation_placeholders(
    tmp_path: Path,
) -> None:
    module = _load_build_module()
    staging = tmp_path / "staging"
    (staging / ".codex-plugin").mkdir(parents=True)
    (staging / ".codex-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    (staging / ".mcp.json").write_text("{}", encoding="utf-8")
    (staging / "README.md").write_text(
        '"BRAVE_API_KEY": "..." <YOUR_API_KEY> ${ENV_NAME}', encoding="utf-8"
    )
    module.scan_staging(staging, {})


def _sync_fixture(module, tmp_path: Path) -> tuple[Path, Path, dict[str, Path]]:
    plugin = tmp_path / "plugin"
    target = plugin / "skills"
    target.mkdir(parents=True)
    (target / "payload.txt").write_text("old", encoding="utf-8")
    source = tmp_path / "canonical.txt"
    source.write_text("new", encoding="utf-8")
    return plugin, target, {"payload.txt": source}


def _hidden_backups(parent: Path) -> list[Path]:
    return [path for path in parent.iterdir() if path.name.startswith(".skills-backup-")]


def _transient_children(parent: Path, target_name: str) -> list[Path]:
    return [
        path for path in parent.iterdir()
        if path.name.startswith(f".{target_name}-staging-")
        or path.name.startswith(f".{target_name}-backup-")
    ]


def test_sync_copy_failure_inside_real_staging_keeps_original_and_removes_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    plugin, target, payload = _sync_fixture(module, tmp_path)
    real_copy2 = module.shutil.copy2

    def fail_copy2(source: Path, destination: Path, *args: object, **kwargs: object) -> Path:
        if Path(source) == payload["payload.txt"]:
            raise OSError("copy2 staging failed")
        return real_copy2(source, destination, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "copy2", fail_copy2)
    with pytest.raises(OSError, match="copy2 staging failed"):
        module._replace_child(target, plugin, payload)
    assert (target / "payload.txt").read_text("utf-8") == "old"
    assert _transient_children(plugin, "skills") == []


def test_sync_keeps_original_target_when_first_swap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    plugin, target, payload = _sync_fixture(module, tmp_path)
    real_replace = module.os.replace

    def fail_first_replace(source: Path, destination: Path) -> None:
        if Path(destination).name.startswith(".skills-backup-"):
            raise OSError("first swap failed")
        real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_first_replace)
    with pytest.raises(OSError, match="first swap failed"):
        module._replace_child(target, plugin, payload)
    assert (target / "payload.txt").read_text("utf-8") == "old"
    assert _hidden_backups(plugin) == []


def test_sync_restores_original_target_when_second_swap_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    plugin, target, payload = _sync_fixture(module, tmp_path)
    real_replace = module.os.replace
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("second swap failed")
        real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_second_replace)
    with pytest.raises(OSError, match="second swap failed"):
        module._replace_child(target, plugin, payload)
    assert (target / "payload.txt").read_text("utf-8") == "old"
    assert _hidden_backups(plugin) == []


def test_sync_keeps_complete_new_target_when_post_commit_backup_cleanup_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    plugin, target, payload = _sync_fixture(module, tmp_path)
    real_rmtree = module.shutil.rmtree

    def fail_backup_cleanup(path: Path, *args: object, **kwargs: object) -> None:
        if Path(path).name.startswith(".skills-backup-"):
            raise OSError("backup cleanup failed")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", fail_backup_cleanup)
    with pytest.raises(OSError, match="backup cleanup failed"):
        module._replace_child(target, plugin, payload)
    assert (target / "payload.txt").read_text("utf-8") == "new"
    assert len(_hidden_backups(plugin)) == 1


def test_sync_retries_partial_post_commit_backup_cleanup_without_replacing_new_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    plugin, target, payload = _sync_fixture(module, tmp_path)
    (target / "second-old.txt").write_text("old", encoding="utf-8")
    real_rmtree = module.shutil.rmtree
    attempts = 0

    def partly_delete_then_fail(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal attempts
        if Path(path).name.startswith(".skills-backup-") and attempts == 0:
            attempts += 1
            next(Path(path).iterdir()).unlink()
            raise OSError("partial backup cleanup failed")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", partly_delete_then_fail)
    module._replace_child(target, plugin, payload)
    assert (target / "payload.txt").read_text("utf-8") == "new"
    assert _transient_children(plugin, "skills") == []


def test_sync_revalidates_backup_containment_before_retrying_recursive_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    parent = tmp_path / "plugin"
    backup = parent / ".skills-backup-synthetic"
    backup.mkdir(parents=True)
    (backup / "old.txt").write_text("old", encoding="utf-8")
    real_strict_child = module._strict_child
    containment_calls = 0
    removal_calls = 0

    def reject_second_containment_check(path: Path, root: Path) -> Path:
        nonlocal containment_calls
        containment_calls += 1
        if containment_calls == 2:
            raise ValueError("second containment check")
        return real_strict_child(path, root)

    def fail_first_removal(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal removal_calls
        removal_calls += 1
        raise OSError("first backup removal failed")

    monkeypatch.setattr(module, "_strict_child", reject_second_containment_check)
    monkeypatch.setattr(module.shutil, "rmtree", fail_first_removal)
    with pytest.raises(ValueError, match="second containment check"):
        module._remove_backup(backup, parent)
    assert containment_calls == 2
    assert removal_calls == 1


def test_sync_write_repairs_post_commit_backup_after_cleanup_condition_clears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    plugin = tmp_path / "plugin"
    skills = plugin / "skills"
    mcp = plugin / "mcp" / "web-research-mcp"
    skills.mkdir(parents=True)
    mcp.mkdir(parents=True)
    (skills / "payload.txt").write_text("old-skills", encoding="utf-8")
    (mcp / "payload.txt").write_text("old-mcp", encoding="utf-8")
    skills_source = tmp_path / "skills-source.txt"
    mcp_source = tmp_path / "mcp-source.txt"
    skills_source.write_text("new-skills", encoding="utf-8")
    mcp_source.write_text("new-mcp", encoding="utf-8")
    monkeypatch.setattr(module, "PLUGIN_ROOT", plugin)
    monkeypatch.setattr(module, "_canonical_skills", lambda: {"payload.txt": skills_source})
    monkeypatch.setattr(module, "_canonical_mcp", lambda: {"payload.txt": mcp_source})
    real_rmtree = module.shutil.rmtree

    def persistently_fail_skills_backup_cleanup(
        path: Path, *args: object, **kwargs: object
    ) -> None:
        if Path(path).name.startswith(".skills-backup-"):
            raise OSError("skills backup cleanup unavailable")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", persistently_fail_skills_backup_cleanup)
    with pytest.raises(OSError, match="skills backup cleanup unavailable"):
        module.write()
    assert (skills / "payload.txt").read_text("utf-8") == "new-skills"
    assert len(_transient_children(plugin, "skills")) == 1
    monkeypatch.setattr(module.shutil, "rmtree", real_rmtree)
    assert module.write() == 0
    assert _transient_children(plugin, "skills") == []
    assert _transient_children(mcp.parent, "web-research-mcp") == []


def test_sync_failure_after_first_target_is_repairable_by_rerunning_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_sync_module()
    plugin = tmp_path / "plugin"
    skills = plugin / "skills"
    mcp = plugin / "mcp" / "web-research-mcp"
    skills.mkdir(parents=True)
    mcp.mkdir(parents=True)
    (skills / "payload.txt").write_text("old-skills", encoding="utf-8")
    (mcp / "payload.txt").write_text("old-mcp", encoding="utf-8")
    skills_source = tmp_path / "skills-source.txt"
    mcp_source = tmp_path / "mcp-source.txt"
    skills_source.write_text("new-skills", encoding="utf-8")
    mcp_source.write_text("new-mcp", encoding="utf-8")
    monkeypatch.setattr(module, "PLUGIN_ROOT", plugin)
    monkeypatch.setattr(module, "_canonical_skills", lambda: {"payload.txt": skills_source})
    monkeypatch.setattr(module, "_canonical_mcp", lambda: {"payload.txt": mcp_source})
    real_replace = module.os.replace

    def fail_mcp_staging_install(source: Path, destination: Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            destination_path == mcp
            and source_path.name.startswith(".web-research-mcp-staging-")
        ):
            raise OSError("mcp staging install failed")
        real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_mcp_staging_install)
    with pytest.raises(OSError, match="mcp staging install failed"):
        module.write()
    monkeypatch.setattr(module.os, "replace", real_replace)
    assert (skills / "payload.txt").read_text("utf-8") == "new-skills"
    assert (mcp / "payload.txt").read_text("utf-8") == "old-mcp"
    assert _transient_children(mcp.parent, "web-research-mcp") == []
    assert module.check() == 1
    assert module.write() == 0
    assert (skills / "payload.txt").read_text("utf-8") == "new-skills"
    assert (mcp / "payload.txt").read_text("utf-8") == "new-mcp"
    assert _transient_children(mcp.parent, "web-research-mcp") == []


@pytest.mark.parametrize("base", [ROOT, PLUGIN])
def test_bilingual_readmes_have_resolving_local_links(base: Path) -> None:
    for name, counterpart in (("README.md", "README.zh-CN.md"), ("README.zh-CN.md", "README.md")):
        contents = (base / name).read_text("utf-8")
        links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", contents)
        assert counterpart in links
        for link in links:
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link) or link.startswith("#"):
                continue
            relative = link.split("#", 1)[0]
            assert (base / relative).exists(), f"broken local link in {base / name}: {link}"


def test_project_plugin_validator_accepts_the_generated_plugin_and_marketplace() -> None:
    validator = ROOT / "scripts" / "validate_plugin.py"
    completed = subprocess.run(
        [sys.executable, str(validator), str(PLUGIN), "--marketplace", str(ROOT / ".agents/plugins/marketplace.json")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Plugin validation passed:" in completed.stdout
