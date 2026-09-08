from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from web_research.models import (
    Direction,
    ErrorCode,
    FetchRequest,
    FetchResult,
    MapResult,
    ResultStatus,
    Route,
    SearchRequest,
    SearchResult,
    SearchSource,
)
from web_research.security import UnsafeUrlError, normalize_public_url


def test_requests_forbid_unknown_fields_and_invalid_enums() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="public transport", unexpected=True)
    with pytest.raises(ValidationError):
        SearchRequest(query="public transport", direction="unknown")


@pytest.mark.parametrize("query", ["", " ", "x" * 2001])
def test_search_request_rejects_empty_or_overlong_query(query: str) -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query=query)


def test_search_request_limits_domains_to_twenty_public_hostnames() -> None:
    valid_domains = [f"site{i}.example.com" for i in range(20)]
    assert SearchRequest(query="q", domains=valid_domains).domains == valid_domains
    with pytest.raises(ValidationError):
        SearchRequest(query="q", domains=valid_domains + ["extra.example.com"])


def test_fixed_enums_remain_closed() -> None:
    assert {item.value for item in Direction} == {
        "auto", "news", "semantic", "academic", "developer"
    }
    assert {item.value for item in Route} == {"primary", "alternate"}
    assert {item.value for item in ResultStatus} == {"SUCCESS", "NO_RESULTS"}
    assert {item.value for item in ErrorCode} == {
        "INVALID_REQUEST", "NOT_CONFIGURED", "AUTH_FAILED", "RATE_LIMITED",
        "QUOTA_EXHAUSTED", "NETWORK_ERROR", "PROVIDER_ERROR",
    }


@pytest.mark.parametrize(
    "url, expected_message",
    [
        ("https://example.com/download?TOKEN=abc", "'TOKEN'"),
        ("https://user:password@example.com/private", "userinfo"),
        ("https://localhost/private", "localhost"),
        ("https://intranet/secret", "single-label"),
        ("http://127.0.0.1/admin", "public"),
        ("http://10.0.0.1/admin", "public"),
        ("http://240.0.0.1/admin", "public"),
        ("https://example.com:8443/path", "port"),
    ],
)
def test_public_url_validation_rejects_unsafe_inputs_without_echoing_url(
    url: str, expected_message: str
) -> None:
    with pytest.raises(UnsafeUrlError) as raised:
        normalize_public_url(url)
    assert expected_message.lower() in str(raised.value).lower()
    assert url not in str(raised.value)


@pytest.mark.parametrize(
    "key",
    ["access_token", "SIG", "signature", "X-Amz-Credential", "x-goog-signature", "GoogleAccessId"],
)
def test_signed_url_query_keys_are_rejected_case_insensitively(key: str) -> None:
    with pytest.raises(UnsafeUrlError) as raised:
        normalize_public_url(f"https://example.com/report?{key}=secret")
    assert key in str(raised.value)
    assert "secret" not in str(raised.value)


def test_public_url_is_normalized_without_fragment() -> None:
    assert normalize_public_url("HTTPS://BÜCHER.example/a?q=one#section") == (
        "https://xn--bcher-kva.example/a?q=one"
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://example.com:80/a?q=one#section", "http://example.com/a?q=one"),
        ("https://example.com:443/a?q=one#section", "https://example.com/a?q=one"),
        ("HTTPS://BÜCHER.example:443/a?q=one#section", "https://xn--bcher-kva.example/a?q=one"),
        ("https://[2001:4860:4860::8888]:443/a?q=one#section", "https://[2001:4860:4860::8888]/a?q=one"),
    ],
)
def test_public_url_normalization_folds_default_ports_but_preserves_path_and_query(
    url: str, expected: str
) -> None:
    assert normalize_public_url(url) == expected


@pytest.mark.parametrize(
    "host",
    ["127.1", "127.000.000.001", "0x7f.0x0.0x0.0x1", "0177.0.0.1", "2130706433", "0x7f000001"],
)
def test_public_url_validation_rejects_noncanonical_numeric_ip_hosts(host: str) -> None:
    with pytest.raises(UnsafeUrlError):
        normalize_public_url(f"http://{host}/private")


def test_result_models_restrict_fetch_and_map_provider_route_subsets() -> None:
    common = {
        "request_id": "a" * 16,
        "status": "SUCCESS",
        "retrieved_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "truncated": False,
    }
    with pytest.raises(ValidationError):
        FetchResult(**common, provider="brave", route_used="primary", url="https://example.com", content="x")
    with pytest.raises(ValidationError):
        MapResult(
            **common,
            provider="exa",
            route_used="primary",
            url="https://example.com",
            urls=["https://example.com/a"],
        )
    with pytest.raises(ValidationError):
        MapResult(
            **common,
            provider="firecrawl",
            route_used="alternate",
            url="https://example.com",
            urls=["https://example.com/a"],
        )


def test_result_models_enforce_bounded_output_and_utc_timestamp() -> None:
    source = SearchSource(
        url="https://example.com/a",
        title="A",
        snippet="x" * 2000,
        source_type="web",
    )
    result = SearchResult(
        request_id="a" * 16,
        status="SUCCESS",
        provider="brave",
        direction="auto",
        route_used="primary",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        truncated=False,
        sources=[source] * 10,
    )
    assert result.retrieved_at.tzinfo == timezone.utc
    with pytest.raises(ValidationError):
        SearchResult.model_validate({**result.model_dump(), "sources": [source] * 11})
    with pytest.raises(ValidationError):
        SearchSource(
            url="https://example.com/a", title="A", snippet="x" * 2001, source_type="web"
        )
    with pytest.raises(ValidationError):
        FetchRequest(url="https://example.com/" + "a" * 8192)
