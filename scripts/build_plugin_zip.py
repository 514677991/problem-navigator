from __future__ import annotations

import hashlib
import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "problem-navigator"
CANONICAL_SKILLS = ROOT / "skills"
CANONICAL_MCP = ROOT / "mcp" / "web-research-mcp"
PROVIDER_KEYS = ("BRAVE_API_KEY", "EXA_API_KEY", "FIRECRAWL_API_KEY")
HARD_CODED_CREDENTIAL = re.compile(
    rb"""(?ix)
    (?<![A-Z0-9_])
    [\"']?(?:BRAVE|EXA|FIRECRAWL)[A-Z0-9_]*(?:KEY|TOKEN)[\"']?
    \s*(?:=|:)\s*
    (?![\"']?(?:\.\.\.|<[^>\r\n]+>|\$\{[^}\r\n]+\})[\"']?)
    [\"']?[A-Z0-9+/_\-.]{16,}={0,2}[\"']?
    """,
)


def production_payload() -> dict[str, Path]:
    """Compose one shared core and optional host discovery metadata."""
    adapter = ROOT / "adapters/generic"
    payload = {
        "release.json": ROOT / "release.json",
        "README.md": adapter / "README.md",
        "README.zh-CN.md": adapter / "README.zh-CN.md",
        "LICENSE": ROOT / "LICENSE",
        "NOTICE.md": ROOT / "NOTICE.md",
    }
    for source in sorted(CANONICAL_SKILLS.rglob("*")):
        if source.is_file() and "agents" not in source.relative_to(CANONICAL_SKILLS).parts and "__pycache__" not in source.parts and source.suffix not in {".pyc", ".pyo"}:
            payload[f"skills/{source.relative_to(CANONICAL_SKILLS).as_posix()}"] = source
    for name in ("pyproject.toml", "uv.lock"):
        payload[f"mcp/web-research-mcp/{name}"] = CANONICAL_MCP / name
    for source in sorted((CANONICAL_MCP / "src").rglob("*.py")):
        relative = source.relative_to(CANONICAL_MCP / "src").as_posix()
        payload[f"mcp/web-research-mcp/src/{relative}"] = source
    payload["HOST_INSTRUCTIONS.md"] = adapter / "HOST_INSTRUCTIONS.md"
    codex = ROOT / "adapters/codex"
    payload[".codex-plugin/plugin.json"] = codex / ".codex-plugin/plugin.json"
    payload[".agents/plugins/marketplace.json"] = ROOT / ".agents/plugins/marketplace.json"
    for name in ("README.md", "README.zh-CN.md"):
        payload[f"adapters/codex/{name}"] = codex / name
    for source in sorted((codex / "skills").glob("*/agents/openai.yaml")):
        payload[source.relative_to(codex).as_posix()] = source
    return payload


def _forbidden_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return (
        any(
            part in {
                "tests", "test", "build", "logs", "log", "cache", "caches",
                "workflow", "workflows", "__pycache__", ".pytest_cache",
            }
            for part in parts
        )
        or any(part.endswith(".egg-info") for part in parts)
        or name.endswith((".log", ".pyc"))
        or name.startswith((".env.", "test_", "workflow.", "cache."))
        or name in {".env", "config.json", "configuration.json", "web-research.json"}
        or (name.startswith("web-research.") and name.endswith(".json"))
    )


def scan_staging(staging: Path, environ: dict[str, str] | os._Environ[str]) -> None:
    """Reject credential material and non-distribution paths without echoing secrets."""
    environment_secrets = [
        value.encode("utf-8")
        for name in PROVIDER_KEYS
        if (value := environ.get(name, ""))
    ]
    for path in sorted(staging.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(staging)
        if _forbidden_path(relative):
            raise ValueError(f"forbidden distribution path: {relative.as_posix()}")
        data = path.read_bytes()
        if any(secret in data for secret in environment_secrets):
            raise ValueError(f"environment secret found in staging: {relative.as_posix()}")
        if HARD_CODED_CREDENTIAL.search(data):
            raise ValueError(f"hard-coded provider credential in staging: {relative.as_posix()}")


def _copy_payload(staging: Path) -> dict[str, Path]:
    payload = production_payload()
    for relative, source in payload.items():
        if not source.is_file():
            raise FileNotFoundError(f"required distribution source is missing: {source}")
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    manifest_path = staging / ".codex-plugin/plugin.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    release = json.loads((ROOT / "release.json").read_text("utf-8"))
    manifest.update({key: release[key] for key in ("name", "version")})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    catalog_path = staging / ".agents/plugins/marketplace.json"
    catalog = json.loads(catalog_path.read_text("utf-8"))
    catalog["plugins"][0]["source"]["path"] = "."
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    # Project release metadata; not a cross-host plugin manifest standard.
    manifest = json.loads((ROOT / "release.json").read_text("utf-8"))
    name, version = manifest["name"], manifest["version"]
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("invalid Plugin name for release filename")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.+-]+)?", version):
        raise ValueError("invalid Plugin version for release filename")
    target = ROOT / "dist" / f"{name}-{version}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="problem-navigator-package-") as temporary:
        staging = Path(temporary)
        payload = _copy_payload(staging)
        scan_staging(staging, os.environ)
        with ZipFile(target, "w", ZIP_DEFLATED, compresslevel=9) as bundle:
            for relative in sorted(payload):
                info = ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = ZIP_DEFLATED
                bundle.writestr(info, (staging / relative).read_bytes(), compresslevel=9)
    checksum = _sha256(target)
    target.with_suffix(".zip.sha256").write_text(f"{checksum}  {target.name}\n", encoding="utf-8", newline="\n")
    print(f"{target.resolve()} sha256={checksum}")


if __name__ == "__main__":
    argparse.ArgumentParser(description="Build the single portable plugin distribution.").parse_args()
    main()
