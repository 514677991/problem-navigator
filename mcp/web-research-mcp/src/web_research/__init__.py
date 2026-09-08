"""Public, transport-independent Research Core API."""

from .config import ConfigSnapshot, StatusResult, configuration_status, load_config
from .core import ResearchCore
from .models import (
    CoreError,
    Direction,
    ErrorCode,
    FetchRequest,
    FetchResult,
    Freshness,
    MapRequest,
    MapResult,
    ResultStatus,
    Route,
    SearchRequest,
    SearchResult,
    SearchSource,
)

__all__ = [
    "ConfigSnapshot",
    "CoreError",
    "Direction",
    "ErrorCode",
    "FetchRequest",
    "FetchResult",
    "Freshness",
    "MapRequest",
    "MapResult",
    "ResearchCore",
    "ResultStatus",
    "Route",
    "SearchRequest",
    "SearchResult",
    "SearchSource",
    "StatusResult",
    "configuration_status",
    "load_config",
]
