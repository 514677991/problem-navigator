"""Pure URL and hostname validation for public-web provider inputs.

This module intentionally performs no DNS lookups.  It validates only URL
syntax and literal IP addresses; a provider's later DNS resolution and
redirect behaviour remain outside this boundary.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit


class UnsafeUrlError(ValueError):
    """A value-free URL safety error suitable for conversion to CoreError."""


_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_NUMERIC_OR_HEX_HOST = re.compile(r"^(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*$")
_SENSITIVE_QUERY_KEYS = frozenset({"token", "access_token", "sig", "signature", "googleaccessid"})


def _unsafe_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or not address.is_global
    )


def normalize_public_hostname(hostname: str) -> str:
    """Return lower-case IDNA hostname, rejecting non-public host syntax."""
    if not isinstance(hostname, str) or not hostname:
        raise UnsafeUrlError("Hostname is required.")
    host = hostname.rstrip(".")
    if not host:
        raise UnsafeUrlError("Hostname is required.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if _unsafe_ip(address):
            raise UnsafeUrlError("Hostname must be publicly routable.")
        return address.compressed
    try:
        encoded = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UnsafeUrlError("Hostname is not valid IDNA.") from exc
    # Some common URL/network parsers interpret abbreviated, octal, hexadecimal,
    # or integer-only hostnames as IPv4.  ``ipaddress`` deliberately rejects
    # those non-canonical forms, so reject them before treating them as DNS.
    if _NUMERIC_OR_HEX_HOST.fullmatch(encoded):
        raise UnsafeUrlError("Numeric hostnames are not allowed.")
    if encoded == "localhost":
        raise UnsafeUrlError("localhost is not allowed.")
    if "." not in encoded:
        raise UnsafeUrlError("Single-label hostnames are not allowed.")
    if len(encoded) > 253 or any(not _HOST_LABEL.fullmatch(label) for label in encoded.split(".")):
        raise UnsafeUrlError("Hostname is invalid.")
    return encoded


def _query_key_is_sensitive(key: str) -> bool:
    folded = key.casefold()
    return (
        folded in _SENSITIVE_QUERY_KEYS
        or folded.startswith("x-amz-")
        or folded.startswith("x-goog-")
    )


def normalize_public_url(url: str) -> str:
    """Validate a public http(s) URL and remove its fragment without I/O."""
    if not isinstance(url, str) or not url or len(url) > 8192:
        raise UnsafeUrlError("URL is invalid.")
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise UnsafeUrlError("URL is invalid.") from exc
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeUrlError("URL scheme must be http or https.")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URL must not include userinfo.")
    if parsed.hostname is None:
        raise UnsafeUrlError("URL must include a hostname.")
    hostname = normalize_public_hostname(parsed.hostname)
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrlError("URL port is invalid.") from exc
    if port is not None and port != (80 if scheme == "http" else 443):
        raise UnsafeUrlError("URL uses a non-default port.")
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if _query_key_is_sensitive(key):
            raise UnsafeUrlError(f"URL query parameter '{key}' is not allowed.")
    host_for_url = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host_for_url if port is None or port == (80 if scheme == "http" else 443) else f"{host_for_url}:{port}"
    return urlunsplit((scheme, netloc, parsed.path, parsed.query, ""))
