from __future__ import annotations

import os
from pathlib import Path

import pytest


EXPLICIT_CONFIGURATION_ENVIRONMENT_VARIABLES = frozenset(
    {
        "BRAVE_API_KEY",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
        "OPENROUTER_API_KEY",
        "TAVILY_API_KEY",
        "TAVILY_API_URL",
        "XAI_API_KEY",
    }
)
CONFIGURATION_ENVIRONMENT_PREFIXES = ("WEB_RESEARCH_", "LEGACY_SEARCH_")


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def clear_configuration_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name in EXPLICIT_CONFIGURATION_ENVIRONMENT_VARIABLES or name.startswith(
            CONFIGURATION_ENVIRONMENT_PREFIXES
        ):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def isolate_user_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    clear_configuration_environment(monkeypatch)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
