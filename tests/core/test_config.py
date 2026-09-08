from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from web_research.config import (
    StatusResult,
    configuration_status,
    load_config,
    user_config_path,
)


def _write_config(path: Path, document: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _status(snapshot: object) -> dict[str, object]:
    return configuration_status(snapshot).model_dump()


def test_missing_file_is_not_configured_and_uses_only_the_given_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    snapshot = load_config(environ={}, path=tmp_path / "missing.json")

    assert user_config_path() == home / ".problem-navigator" / "web-research.json"
    assert _status(snapshot) == {
        "config_state": "NOT_CONFIGURED",
        "providers": {
            "brave": "NOT_CONFIGURED",
            "exa": "NOT_CONFIGURED",
            "firecrawl": "NOT_CONFIGURED",
        },
        "capabilities": {
            "search": "NOT_CONFIGURED",
            "news": "NOT_CONFIGURED",
            "semantic": "NOT_CONFIGURED",
            "academic": "NOT_CONFIGURED",
            "developer": "NOT_CONFIGURED",
            "fetch": "NOT_CONFIGURED",
            "map": "NOT_CONFIGURED",
        },
    }


def test_valid_v1_file_trims_keys_and_derives_every_capability(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path / "web-research.json",
        {
            "schema_version": 1,
            "brave": {"api_key": " brave-file-key "},
            "exa": {"api_key": "exa-file-key"},
            "firecrawl": {"api_key": "firecrawl-file-key"},
        },
    )

    snapshot = load_config(environ={}, path=path)

    assert snapshot.brave_api_key == "brave-file-key"
    assert snapshot.exa_api_key == "exa-file-key"
    assert snapshot.firecrawl_api_key == "firecrawl-file-key"
    assert _status(snapshot) == {
        "config_state": "VALID",
        "providers": {
            "brave": "CONFIGURED",
            "exa": "CONFIGURED",
            "firecrawl": "CONFIGURED",
        },
        "capabilities": {
            "search": "CONFIGURED",
            "news": "CONFIGURED",
            "semantic": "CONFIGURED",
            "academic": "CONFIGURED",
            "developer": "CONFIGURED",
            "fetch": "CONFIGURED",
            "map": "CONFIGURED",
        },
    }


@pytest.mark.parametrize(
    "document",
    [
        "{not json",
        {"schema_version": 1, "unknown": {"api_key": "secret"}},
        {"schema_version": 1, "brave": {"api_key": "secret", "extra": True}},
        {"schema_version": 2, "brave": {"api_key": "secret"}},
        {"schema_version": 1, "brave": {"api_key": "   "}},
        {"schema_version": 1, "brave": {"api_key": "has\u0000control"}},
    ],
    ids=["invalid-json", "unknown-top-level", "unknown-provider-field", "wrong-version", "empty-key", "control-key"],
)
def test_invalid_file_is_ignored_as_a_whole(tmp_path: Path, document: object) -> None:
    path = tmp_path / "web-research.json"
    path.write_text(document if isinstance(document, str) else json.dumps(document), encoding="utf-8")

    snapshot = load_config(environ={}, path=path)

    assert snapshot.brave_api_key is None
    assert snapshot.exa_api_key is None
    assert snapshot.firecrawl_api_key is None
    assert _status(snapshot)["config_state"] == "INVALID"


def test_existing_unreadable_config_path_is_invalid_not_missing(tmp_path: Path) -> None:
    path = tmp_path / "web-research.json"
    path.mkdir()

    snapshot = load_config(environ={}, path=path)

    assert _status(snapshot)["config_state"] == "INVALID"


def test_environment_overrides_only_its_provider_value(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path / "web-research.json",
        {
            "schema_version": 1,
            "brave": {"api_key": "brave-file-key"},
            "exa": {"api_key": "exa-file-key"},
            "firecrawl": {"api_key": "firecrawl-file-key"},
        },
    )

    snapshot = load_config(
        environ={"EXA_API_KEY": " exa-environment-key "}, path=path
    )

    assert snapshot.brave_api_key == "brave-file-key"
    assert snapshot.exa_api_key == "exa-environment-key"
    assert snapshot.firecrawl_api_key == "firecrawl-file-key"


def test_invalid_file_does_not_block_a_valid_environment_provider(tmp_path: Path) -> None:
    path = _write_config(tmp_path / "web-research.json", {"schema_version": 99})

    snapshot = load_config(environ={"EXA_API_KEY": "environment-key"}, path=path)

    status = _status(snapshot)
    assert status["config_state"] == "INVALID"
    assert status["providers"] == {
        "brave": "NOT_CONFIGURED",
        "exa": "CONFIGURED",
        "firecrawl": "NOT_CONFIGURED",
    }
    assert status["capabilities"] == {
        "search": "CONFIGURED",
        "news": "CONFIGURED",
        "semantic": "CONFIGURED",
        "academic": "CONFIGURED",
        "developer": "NOT_CONFIGURED",
        "fetch": "CONFIGURED",
        "map": "NOT_CONFIGURED",
    }


def test_valid_environment_configuration_needs_no_file_and_ignores_legacy_names(
    tmp_path: Path,
) -> None:
    snapshot = load_config(
        environ={
            "BRAVE_API_KEY": "brave-environment-key",
            "LEGACY_SEARCH_API_KEY": "must-not-be-read",
            "WEB_RESEARCH_API_KEY": "must-not-be-read",
            "TAVILY_API_KEY": "must-not-be-read",
            "OPENROUTER_API_KEY": "must-not-be-read",
        },
        path=tmp_path / "missing.json",
    )

    status = _status(snapshot)
    assert snapshot.brave_api_key == "brave-environment-key"
    assert snapshot.exa_api_key is None
    assert snapshot.firecrawl_api_key is None
    assert status["config_state"] == "VALID"
    assert status["capabilities"]["search"] == "CONFIGURED"
    assert status["capabilities"]["semantic"] == "NOT_CONFIGURED"
    assert status["capabilities"]["map"] == "NOT_CONFIGURED"


def test_empty_or_invalid_environment_key_overrides_file_with_not_configured(
    tmp_path: Path,
) -> None:
    path = _write_config(
        tmp_path / "web-research.json",
        {"schema_version": 1, "brave": {"api_key": "brave-file-key"}},
    )

    snapshot = load_config(environ={"BRAVE_API_KEY": " \t "}, path=path)

    assert snapshot.brave_api_key is None
    assert _status(snapshot)["providers"]["brave"] == "NOT_CONFIGURED"


def test_status_is_offline_and_serialization_never_contains_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "very-secret-value-that-must-never-appear"
    snapshot = load_config(environ={"FIRECRAWL_API_KEY": secret}, path=tmp_path / "missing.json")

    def forbid_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("configuration status must not use the network")

    monkeypatch.setattr(socket, "create_connection", forbid_network)
    monkeypatch.setattr(socket, "socket", forbid_network)

    status = configuration_status(snapshot)
    serialized = status.model_dump_json()

    assert status.capabilities.map == "CONFIGURED"
    assert secret not in serialized
    assert "mask" not in serialized.lower()
    assert "length" not in serialized.lower()
    assert str(tmp_path) not in serialized


@pytest.mark.parametrize(
    "providers, capabilities",
    [
        (
            {"brave": "CONFIGURED", "exa": "NOT_CONFIGURED"},
            {
                "search": "CONFIGURED",
                "news": "CONFIGURED",
                "semantic": "NOT_CONFIGURED",
                "academic": "NOT_CONFIGURED",
                "developer": "CONFIGURED",
                "fetch": "NOT_CONFIGURED",
                "map": "NOT_CONFIGURED",
            },
        ),
        (
            {
                "brave": "CONFIGURED",
                "exa": "NOT_CONFIGURED",
                "firecrawl": "NOT_CONFIGURED",
                "unexpected": "CONFIGURED",
            },
            {
                "search": "CONFIGURED",
                "news": "CONFIGURED",
                "semantic": "NOT_CONFIGURED",
                "academic": "NOT_CONFIGURED",
                "developer": "CONFIGURED",
                "fetch": "NOT_CONFIGURED",
                "map": "NOT_CONFIGURED",
            },
        ),
        (
            {
                "brave": "CONFIGURED",
                "exa": "NOT_CONFIGURED",
                "firecrawl": "NOT_CONFIGURED",
            },
            {
                "search": "CONFIGURED",
                "news": "CONFIGURED",
                "semantic": "NOT_CONFIGURED",
                "academic": "NOT_CONFIGURED",
                "developer": "CONFIGURED",
                "fetch": "NOT_CONFIGURED",
            },
        ),
        (
            {
                "brave": "CONFIGURED",
                "exa": "NOT_CONFIGURED",
                "firecrawl": "NOT_CONFIGURED",
            },
            {
                "search": "CONFIGURED",
                "news": "CONFIGURED",
                "semantic": "NOT_CONFIGURED",
                "academic": "NOT_CONFIGURED",
                "developer": "CONFIGURED",
                "fetch": "NOT_CONFIGURED",
                "map": "NOT_CONFIGURED",
                "unexpected": "CONFIGURED",
            },
        ),
    ],
    ids=["missing-provider", "extra-provider", "missing-capability", "extra-capability"],
)
def test_status_result_rejects_any_missing_or_extra_fixed_output_key(
    providers: dict[str, str], capabilities: dict[str, str]
) -> None:
    with pytest.raises(ValidationError):
        StatusResult(
            config_state="VALID", providers=providers, capabilities=capabilities
        )


def test_status_result_json_schema_has_closed_provider_and_capability_objects() -> None:
    schema = StatusResult.model_json_schema()
    definitions = schema["$defs"]
    providers = definitions["ProviderStatus"]
    capabilities = definitions["CapabilityStatus"]

    assert providers["additionalProperties"] is False
    assert providers["required"] == ["brave", "exa", "firecrawl"]
    assert set(providers["properties"]) == {"brave", "exa", "firecrawl"}
    assert capabilities["additionalProperties"] is False
    assert capabilities["required"] == [
        "search", "news", "semantic", "academic", "developer", "fetch", "map"
    ]
    assert set(capabilities["properties"]) == {
        "search", "news", "semantic", "academic", "developer", "fetch", "map"
    }
