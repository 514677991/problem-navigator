from __future__ import annotations

import tomllib
from pathlib import Path


def test_package_metadata_is_020(project_root: Path) -> None:
    data = tomllib.loads(
        (project_root / "mcp/web-research-mcp/pyproject.toml").read_text("utf-8")
    )

    assert data["project"]["version"] == "0.2.0"
    assert set(data["project"]["scripts"]) == {"web-research"}
    assert "questionary" not in " ".join(data["project"]["dependencies"])
    assert "tenacity" not in " ".join(data["project"]["dependencies"])
    assert not list((project_root / "mcp/web-research-mcp/tests").glob("test_*.py"))
