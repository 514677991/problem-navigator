from __future__ import annotations

import importlib
import os
from pathlib import Path

import conftest as test_conftest


ISOLATED_ENVIRONMENT_VARIABLES = frozenset(
    {
        "BRAVE_API_KEY",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
        "LEGACY_SEARCH_API_KEY",
        "LEGACY_SEARCH_API_URL",
        "LEGACY_SEARCH_MODEL",
        "LEGACY_SEARCH_OPENROUTER_REFERER",
        "LEGACY_SEARCH_OPENROUTER_TITLE",
        "LEGACY_SEARCH_PROVIDER",
        "OPENROUTER_API_KEY",
        "TAVILY_API_KEY",
        "TAVILY_API_URL",
        "WEB_RESEARCH_API_KEY",
        "WEB_RESEARCH_API_URL",
        "WEB_RESEARCH_MODEL",
        "WEB_RESEARCH_OPENROUTER_REFERER",
        "WEB_RESEARCH_OPENROUTER_TITLE",
        "WEB_RESEARCH_PROVIDER",
        "XAI_API_KEY",
    }
)


def test_configuration_cleanup_helper_removes_all_configuration_environment(
    monkeypatch,
) -> None:
    cleanup = getattr(test_conftest, "clear_configuration_environment", None)
    assert callable(cleanup)

    future_configuration_options = {
        "WEB_RESEARCH_FUTURE_OPTION",
        "LEGACY_SEARCH_FUTURE_OPTION",
    }
    for name in ISOLATED_ENVIRONMENT_VARIABLES | future_configuration_options:
        monkeypatch.setenv(name, "test-secret")
    monkeypatch.setenv("UNRELATED_TEST_VARIABLE", "preserved")

    cleanup(monkeypatch)

    assert not ISOLATED_ENVIRONMENT_VARIABLES.intersection(os.environ)
    assert "WEB_RESEARCH_FUTURE_OPTION" not in os.environ
    assert "LEGACY_SEARCH_FUTURE_OPTION" not in os.environ
    assert os.environ["UNRELATED_TEST_VARIABLE"] == "preserved"

    config_module = importlib.import_module("web_research.config")
    snapshot = config_module.load_config()
    status = config_module.configuration_status(snapshot)

    assert snapshot.brave_api_key is None
    assert snapshot.exa_api_key is None
    assert snapshot.firecrawl_api_key is None
    assert status.config_state == "NOT_CONFIGURED"
    assert Path.home() == Path(os.environ["HOME"])


def test_automatic_fixture_delegates_cleanup_and_redirects_homes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = []

    def fake_cleanup(received_monkeypatch) -> None:
        calls.append(received_monkeypatch)

    monkeypatch.setattr(
        test_conftest,
        "clear_configuration_environment",
        fake_cleanup,
        raising=False,
    )

    fixture_tmp_path = tmp_path / "fixture"
    fixture_tmp_path.mkdir()
    test_conftest.isolate_user_configuration.__wrapped__(monkeypatch, fixture_tmp_path)

    assert calls == [monkeypatch]
    home = fixture_tmp_path / "home"
    assert os.environ["HOME"] == str(home)
    assert os.environ["USERPROFILE"] == str(home)
    assert Path.home() == home
