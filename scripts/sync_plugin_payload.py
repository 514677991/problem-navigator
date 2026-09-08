from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "problem-navigator"
CANONICAL_SKILLS = ROOT / "skills"
CANONICAL_MCP = ROOT / "mcp" / "web-research-mcp"


def _strict_child(path: Path, parent: Path) -> Path:
    resolved_path = path.resolve()
    resolved_parent = parent.resolve()
    if resolved_path == resolved_parent or resolved_parent not in resolved_path.parents:
        raise ValueError(f"refusing path outside intended plugin root: {resolved_path}")
    return resolved_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_skills() -> dict[str, Path]:
    payload = {
        path.relative_to(CANONICAL_SKILLS).as_posix(): path
        for path in sorted(CANONICAL_SKILLS.rglob("*"))
        if path.is_file() and "agents" not in path.relative_to(CANONICAL_SKILLS).parts and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}
    }
    overlay = ROOT / "adapters/codex/skills"
    payload.update({path.relative_to(overlay).as_posix(): path
                    for path in sorted(overlay.glob("*/agents/openai.yaml"))})
    return payload


def _canonical_mcp() -> dict[str, Path]:
    payload = {name: CANONICAL_MCP / name for name in ("pyproject.toml", "uv.lock")}
    payload.update({
        (Path("src") / path.relative_to(CANONICAL_MCP / "src")).as_posix(): path
        for path in sorted((CANONICAL_MCP / "src").rglob("*.py"))
    })
    return payload


def _destination_files(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _matches(source: dict[str, Path], destination: Path) -> bool:
    current = _destination_files(destination)
    return set(source) == set(current) and all(
        _sha256(source[name]) == _sha256(current[name]) for name in source
    )


def _stage_payload(parent: Path, label: str, payload: dict[str, Path]) -> Path:
    staging = Path(tempfile.mkdtemp(prefix=f".{label}-staging-", dir=parent))
    _strict_child(staging, parent)
    try:
        for relative, source in payload.items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    except BaseException:
        _strict_child(staging, parent)
        shutil.rmtree(staging)
        raise
    return staging


def _remove_backup(backup: Path, parent: Path) -> None:
    """Remove a contained post-commit backup, retrying one transient filesystem error."""
    for attempt in range(2):
        if not backup.exists():
            return
        backup = _strict_child(backup, parent)
        try:
            shutil.rmtree(backup)
            return
        except OSError:
            if attempt:
                raise


def _clean_post_commit_backups(target: Path, parent: Path) -> None:
    """Clear leftovers only while an existing target is already authoritative."""
    if not target.exists():
        return
    for backup in sorted(target.parent.glob(f".{target.name}-backup-*")):
        _remove_backup(backup, parent)


def _replace_child(target: Path, parent: Path, payload: dict[str, Path]) -> None:
    """Replace one child; staging installation is its commit point.

    Failures before installing the complete staging tree restore the intact old
    target. Once the staging tree is installed, the complete new target is
    authoritative; backup cleanup is post-commit housekeeping.
    """
    target = _strict_child(target, parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    _clean_post_commit_backups(target, parent)
    staging = _stage_payload(target.parent, target.name, payload)
    backup: Path | None = None
    installed = False
    try:
        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{target.name}-backup-", dir=target.parent))
            _strict_child(backup, parent)
            backup.rmdir()
            os.replace(target, backup)
        os.replace(staging, target)
        installed = True
        if backup is not None:
            _remove_backup(backup, parent)
            backup = None
    except BaseException:
        if not installed and backup is not None and backup.exists():
            if target.exists():
                _strict_child(target, parent)
                shutil.rmtree(target)
            os.replace(backup, target)
        raise
    finally:
        if staging.exists():
            _strict_child(staging, parent)
            shutil.rmtree(staging)


def _metadata_payload() -> dict[str, bytes]:
    adapter = ROOT / "adapters/codex"
    payload = {name: (ROOT / name).read_bytes() for name in ("LICENSE", "NOTICE.md", "release.json")}
    payload.update({name: (ROOT / "adapters/generic" / name).read_bytes()
                    for name in ("README.md", "README.zh-CN.md", "HOST_INSTRUCTIONS.md")})
    payload.update({f"adapters/codex/{name}": (adapter / name).read_bytes()
                    for name in ("README.md", "README.zh-CN.md")})
    release = json.loads(payload["release.json"])
    manifest = json.loads((adapter / ".codex-plugin/plugin.json").read_text("utf-8"))
    manifest.update({key: release[key] for key in ("name", "version")})
    payload[".codex-plugin/plugin.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text("utf-8"))
    catalog["plugins"][0]["source"]["path"] = "."
    payload[".agents/plugins/marketplace.json"] = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return payload


def check() -> int:
    valid = _matches(_canonical_skills(), PLUGIN_ROOT / "skills") and _matches(
        _canonical_mcp(), PLUGIN_ROOT / "mcp" / "web-research-mcp"
    )
    obsolete = PLUGIN_ROOT / ".mcp.json"
    valid = valid and not (obsolete.exists() or obsolete.is_symlink()) and all(
        (PLUGIN_ROOT / name).is_file()
        and data == (PLUGIN_ROOT / name).read_bytes()
        for name, data in _metadata_payload().items()
    )
    if not valid:
        print("plugin payload is out of sync")
        return 1
    print("plugin payload is in sync")
    return 0


def write() -> int:
    """Commit each target independently; rerun --write after a failed pair or cleanup."""
    plugin = PLUGIN_ROOT.resolve()
    _replace_child(PLUGIN_ROOT / "skills", plugin, _canonical_skills())
    _replace_child(PLUGIN_ROOT / "mcp" / "web-research-mcp", plugin, _canonical_mcp())
    for name, data in _metadata_payload().items():
        destination = _strict_child(PLUGIN_ROOT / name, plugin)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=f".{destination.name}-", dir=destination.parent, delete=False) as temporary:
            staging = _strict_child(Path(temporary.name), plugin)
        try:
            staging.write_bytes(data)
            os.replace(staging, destination)
        finally:
            if staging.exists():
                _strict_child(staging, plugin).unlink()
    obsolete = PLUGIN_ROOT / ".mcp.json"
    if obsolete.exists() or obsolete.is_symlink():
        _strict_child(obsolete, plugin)
        obsolete.unlink()
    return check()


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize the generated Plugin payload.")
    choices = parser.add_mutually_exclusive_group(required=True)
    choices.add_argument("--write", action="store_true")
    choices.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return write() if args.write else check()


if __name__ == "__main__":
    raise SystemExit(main())
