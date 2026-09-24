"""AXIS base-URL configuration: one validator shared by every AXIS call path.

Resolution happens at the AXIS request boundary only, never at import or
construction time, so Sapphire can start (and non-AXIS flows can run) without
AXIS configured. Error messages never echo the supplied URL.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

AXIS_BASE_URL_ENV = "AXIS_BASE_URL"
AXIS_NOT_CONFIGURED = "axis_not_configured"
AXIS_API_PREFIX = "/api/v2/"

# Plain HTTP is only permitted to the local machine.
LOCAL_HTTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

_REASON_MESSAGES = {
    "missing": f"AXIS base URL is not configured. Set {AXIS_BASE_URL_ENV}.",
    "whitespace_not_allowed": "AXIS base URL is invalid: it must not contain whitespace.",
    "malformed_url": "AXIS base URL is invalid: it could not be parsed (check brackets around IPv6 hosts).",
    "invalid_scheme": "AXIS base URL is invalid: scheme must be http or https.",
    "missing_host": "AXIS base URL is invalid: a host is required.",
    "invalid_port": "AXIS base URL is invalid: the port is not valid.",
    "credentials_not_allowed": "AXIS base URL is invalid: credentials are not allowed.",
    "query_or_fragment_not_allowed": "AXIS base URL is invalid: query strings and fragments are not allowed.",
    "path_not_allowed": "AXIS base URL is invalid: it must not include a path; AXIS endpoint paths are added by Sapphire.",
    "https_required": "AXIS base URL is invalid: HTTPS is required except for localhost, 127.0.0.1 and ::1.",
}

_WHITESPACE = re.compile(r"\s")


class AxisConfigError(ValueError):
    """Raised when the AXIS base URL is missing or invalid.

    `reason` is a stable machine-readable code; the message is safe to show
    and never contains the configured value.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(_REASON_MESSAGES[reason])


def validate_axis_base_url(value: object) -> str:
    """Return the normalized base URL (scheme://host[:port]) or raise AxisConfigError."""
    if not isinstance(value, str) or not value.strip():
        raise AxisConfigError("missing")

    candidate = value.strip()
    if _WHITESPACE.search(candidate):
        raise AxisConfigError("whitespace_not_allowed")

    # urlsplit and .hostname raise ValueError on malformed input (e.g. an
    # unbalanced or non-IP "[...]" host); their messages can echo the input,
    # so they are replaced with a fixed, safe reason.
    try:
        parts = urlsplit(candidate)
        host = parts.hostname
    except ValueError:
        raise AxisConfigError("malformed_url") from None

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise AxisConfigError("invalid_scheme")

    if parts.username is not None or parts.password is not None:
        raise AxisConfigError("credentials_not_allowed")

    if not host:
        raise AxisConfigError("missing_host")

    try:
        parts.port
    except ValueError:
        raise AxisConfigError("invalid_port") from None

    if "?" in candidate or "#" in candidate:
        raise AxisConfigError("query_or_fragment_not_allowed")

    if parts.path not in ("", "/"):
        raise AxisConfigError("path_not_allowed")

    if scheme == "http" and host not in LOCAL_HTTP_HOSTS:
        raise AxisConfigError("https_required")

    return f"{scheme}://{parts.netloc}"


def resolve_axis_base_url(explicit: str | None = None) -> str:
    """Validate an explicitly supplied base URL, or AXIS_BASE_URL when none is given."""
    value = explicit if explicit is not None else os.environ.get(AXIS_BASE_URL_ENV)
    return validate_axis_base_url(value)


def build_axis_url(base_url: str, endpoint_path: str) -> str:
    """Join a validated base URL and an /api/v2/ endpoint path exactly once."""
    if not isinstance(endpoint_path, str) or not endpoint_path.startswith(AXIS_API_PREFIX):
        raise ValueError("AXIS endpoint path must start with /api/v2/.")
    return f"{validate_axis_base_url(base_url)}{endpoint_path}"
