"""The three fixed provider adapters used by the research core."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ..config import ConfigSnapshot
from .base import ProviderTransport
from .brave import BraveProvider
from .exa import ExaProvider
from .firecrawl import FirecrawlProvider


def configured_providers(
    snapshot: ConfigSnapshot,
    transport: ProviderTransport,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Build only adapters backed by a configured key."""
    providers: dict[str, object] = {}
    if snapshot.brave_api_key is not None:
        providers["brave"] = BraveProvider(snapshot.brave_api_key, transport, clock=clock)
    if snapshot.exa_api_key is not None:
        providers["exa"] = ExaProvider(snapshot.exa_api_key, transport, clock=clock)
    if snapshot.firecrawl_api_key is not None:
        providers["firecrawl"] = FirecrawlProvider(
            snapshot.firecrawl_api_key, transport, clock=clock
        )
    return providers


__all__ = [
    "BraveProvider",
    "ExaProvider",
    "FirecrawlProvider",
    "ProviderTransport",
    "configured_providers",
]
