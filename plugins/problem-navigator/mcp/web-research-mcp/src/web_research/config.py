"""Strict, local-only configuration for the public-web research core."""

from __future__ import annotations

import json
import os
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


_ENVIRONMENT_KEYS = {
    "brave": "BRAVE_API_KEY",
    "exa": "EXA_API_KEY",
    "firecrawl": "FIRECRAWL_API_KEY",
}
_PROVIDERS = tuple(_ENVIRONMENT_KEYS)
_CONFIGURED = "CONFIGURED"
_NOT_CONFIGURED = "NOT_CONFIGURED"

ConfigState = Literal["VALID", "NOT_CONFIGURED", "INVALID"]
ConfigurationValue = Literal["CONFIGURED", "NOT_CONFIGURED"]


def _normalized_key(value: object) -> str | None:
    """Return a usable key without accepting whitespace or control characters."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not 1 <= len(normalized) <= 4096:
        return None
    if any(unicodedata.category(character) == "Cc" for character in normalized):
        return None
    return normalized


class _ProviderFileConfig(BaseModel):
    """One provider's only supported on-disk setting."""

    model_config = ConfigDict(extra="forbid", strict=True)

    api_key: str

    @field_validator("api_key")
    @classmethod
    def _api_key_is_usable(cls, value: str) -> str:
        normalized = _normalized_key(value)
        if normalized is None:
            raise ValueError("api_key must be a non-empty, control-free value")
        return normalized


class _FileConfig(BaseModel):
    """Version 1 of the entire supported user-configuration document."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: int
    brave: _ProviderFileConfig | None = None
    exa: _ProviderFileConfig | None = None
    firecrawl: _ProviderFileConfig | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def _schema_version_is_exactly_one(cls, value: object) -> int:
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be 1")
        return value


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    """Resolved keys plus the file-validity bit needed for safe status output."""

    brave_api_key: str | None = field(default=None, repr=False)
    exa_api_key: str | None = field(default=None, repr=False)
    firecrawl_api_key: str | None = field(default=None, repr=False)
    file_invalid: bool = False


class _StatusModel(BaseModel):
    """Base class for immutable, closed status-output objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderStatus(_StatusModel):
    """The fixed set of provider readiness values."""

    brave: ConfigurationValue
    exa: ConfigurationValue
    firecrawl: ConfigurationValue


class CapabilityStatus(_StatusModel):
    """The fixed set of capability readiness values."""

    search: ConfigurationValue
    news: ConfigurationValue
    semantic: ConfigurationValue
    academic: ConfigurationValue
    developer: ConfigurationValue
    fetch: ConfigurationValue
    map: ConfigurationValue


class StatusResult(_StatusModel):
    """The deliberately secret-free configuration status contract."""

    config_state: ConfigState
    providers: ProviderStatus
    capabilities: CapabilityStatus


def user_config_path() -> Path:
    """Return the sole supported user configuration location."""
    return Path.home() / ".problem-navigator" / "web-research.json"


def _load_file_values(path: Path) -> tuple[dict[str, str | None], bool]:
    """Load a whole file atomically from a validity perspective, never partially."""
    empty_values: dict[str, str | None] = {provider: None for provider in _PROVIDERS}
    try:
        exists = path.exists()
    except OSError:
        return empty_values, True
    if not exists:
        return empty_values, False

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        parsed = _FileConfig.model_validate(document)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError):
        return empty_values, True

    return {
        provider: getattr(parsed, provider).api_key
        if getattr(parsed, provider) is not None
        else None
        for provider in _PROVIDERS
    }, False


def load_config(
    environ: Mapping[str, str] | None = None, path: Path | None = None
) -> ConfigSnapshot:
    """Resolve only the three provider variables and the v1 configuration file.

    A present environment variable supersedes just its provider's file value.
    An unusable environment value deliberately leaves that provider unconfigured.
    """
    environment = os.environ if environ is None else environ
    file_values, file_invalid = _load_file_values(path or user_config_path())
    resolved: dict[str, str | None] = dict(file_values)
    for provider, environment_name in _ENVIRONMENT_KEYS.items():
        if environment_name in environment:
            resolved[provider] = _normalized_key(environment[environment_name])
    return ConfigSnapshot(
        brave_api_key=resolved["brave"],
        exa_api_key=resolved["exa"],
        firecrawl_api_key=resolved["firecrawl"],
        file_invalid=file_invalid,
    )


def configuration_status(snapshot: ConfigSnapshot) -> StatusResult:
    """Derive the fixed status matrix without constructing clients or adapters."""
    brave = snapshot.brave_api_key is not None
    exa = snapshot.exa_api_key is not None
    firecrawl = snapshot.firecrawl_api_key is not None

    def state(configured: bool) -> ConfigurationValue:
        return _CONFIGURED if configured else _NOT_CONFIGURED

    if snapshot.file_invalid:
        config_state: ConfigState = "INVALID"
    elif brave or exa or firecrawl:
        config_state = "VALID"
    else:
        config_state = "NOT_CONFIGURED"

    return StatusResult(
        config_state=config_state,
        providers={
            "brave": state(brave),
            "exa": state(exa),
            "firecrawl": state(firecrawl),
        },
        capabilities={
            "search": state(brave or exa),
            "news": state(brave or exa),
            "semantic": state(exa),
            "academic": state(firecrawl or exa),
            "developer": state(firecrawl or brave),
            "fetch": state(firecrawl or exa),
            "map": state(firecrawl),
        },
    )
