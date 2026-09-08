"""Approval-gated, one-request smoke check for one explicitly chosen provider."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx

from web_research.config import load_config
from web_research.core import ResearchCore
from web_research.models import CoreError
from web_research.providers import ProviderTransport


REQUESTS = {
    "brave": {"direction": "auto", "route": "primary"},
    "exa": {"direction": "semantic", "route": "primary"},
    "firecrawl": {"direction": "developer", "route": "primary"},
}
KEY_ATTRIBUTES = {
    "brave": "brave_api_key",
    "exa": "exa_api_key",
    "firecrawl": "firecrawl_api_key",
}


async def smoke(provider: str) -> int:
    snapshot = load_config()
    if getattr(snapshot, KEY_ATTRIBUTES[provider]) is None:
        print(json.dumps({"provider": provider, "status": "NOT_CONFIGURED", "source_count": 0}))
        return 2
    async with httpx.AsyncClient() as client:
        core = ResearchCore.from_config(snapshot, transport=ProviderTransport(client))
        try:
            result = await core.search("public web research capability check", **REQUESTS[provider])
        except CoreError as error:
            print(json.dumps({"provider": provider, "request_id": error.request_id, "status": error.code.value, "source_count": 0}))
            return 1
    print(json.dumps({"provider": provider, "request_id": result.request_id, "status": result.status.value, "source_count": len(result.sources)}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(REQUESTS), required=True)
    arguments = parser.parse_args()
    sys.exit(asyncio.run(smoke(arguments.provider)))
