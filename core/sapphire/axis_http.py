"""Strict HTTP transport for Sapphire -> AXIS requests.

One request per call, redirects never followed, no retries. The outcome is
decided by HTTP status first (3xx -> redirect, >= 400 -> http_error); only a
2xx body is inspected, and it must be a JSON object with top-level ``ok`` True
and an object ``data`` (the AXIS v1 envelope). Endpoint-specific checks (for
example execute's ``data.sessionId``) belong to the caller.

Failures carry only a kind, the HTTP status and, for configuration errors, a
fixed reason code. Response bodies, URLs, hosts, headers and exception text
are never returned or logged.

Service credentials (S3) are read from the environment at request time, never
cached, and attached here only: ``Authorization: Bearer`` on POST
/api/v2/execute, and ``x-vercel-protection-bypass`` on every request when
configured. Neither is attached unless the base URL is https or loopback.
Missing or malformed credentials fail closed before any request.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import requests

from core.sapphire.axis_config import (
    LOCAL_HTTP_HOSTS,
    AxisConfigError,
    build_axis_url,
    resolve_axis_base_url,
)
from core.sapphire.axis_contract import EXECUTE_ENDPOINT

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20

KIND_SUCCESS = "success"
KIND_NOT_CONFIGURED = "not_configured"
KIND_REDIRECT = "redirect"
KIND_HTTP_ERROR = "http_error"
KIND_TIMEOUT = "timeout"
KIND_CONNECTION_ERROR = "connection_error"
KIND_NON_JSON = "non_json"
KIND_NOT_OK = "not_ok"
KIND_AUTH_NOT_CONFIGURED = "auth_not_configured"
KIND_BYPASS_INVALID = "bypass_invalid"
KIND_INSECURE_TRANSPORT = "insecure_transport"

AXIS_SERVICE_TOKEN_ENV = "AXIS_SERVICE_TOKEN"
VERCEL_PROTECTION_BYPASS_ENV = "VERCEL_PROTECTION_BYPASS_SECRET"
MIN_SERVICE_TOKEN_LENGTH = 32

AUTHORIZATION_HEADER = "Authorization"
VERCEL_BYPASS_HEADER = "x-vercel-protection-bypass"
_CREDENTIAL_HEADERS = frozenset({AUTHORIZATION_HEADER.lower(), VERCEL_BYPASS_HEADER})

# Visible ASCII only: no whitespace, no control characters, nothing a header
# encoder could reject (its error text could echo the value).
_CREDENTIAL_VALUE = re.compile(r"[\x21-\x7e]+")


@dataclass(frozen=True)
class AxisResult:
    kind: str
    status: int | None = None
    data: dict[str, Any] | None = None
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.kind == KIND_SUCCESS


def _finish(kind: str, status: int | None = None, data: dict | None = None, reason: str | None = None) -> AxisResult:
    if kind != KIND_SUCCESS:
        logger.warning("[AXIS_HTTP] request failed kind=%s status=%s", kind, status)
    return AxisResult(kind=kind, status=status, data=data, reason=reason)


def _is_secure_transport(base_url: str) -> bool:
    """True for https, or for a loopback host (the only plain-HTTP hosts axis_config allows)."""
    parts = urlsplit(base_url)
    return parts.scheme.lower() == "https" or parts.hostname in LOCAL_HTTP_HOSTS


def _service_token() -> str | None:
    """AXIS_SERVICE_TOKEN, trimmed, or None when missing, short or malformed."""
    token = os.environ.get(AXIS_SERVICE_TOKEN_ENV, "").strip()
    if len(token) < MIN_SERVICE_TOKEN_LENGTH or not _CREDENTIAL_VALUE.fullmatch(token):
        return None
    return token


def _bypass_secret() -> tuple[str | None, bool]:
    """(secret, valid). Unset or empty -> (None, True); set but malformed -> (None, False)."""
    secret = os.environ.get(VERCEL_PROTECTION_BYPASS_ENV)
    if not secret:
        return None, True
    if not _CREDENTIAL_VALUE.fullmatch(secret):
        return None, False
    return secret, True


def request_axis(
    method: str,
    endpoint_path: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any] | None = None,
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> AxisResult:
    """Send one AXIS request and classify the response.

    ``endpoint_path`` must be an ``/api/v2/...`` path; ``base_url`` defaults to
    AXIS_BASE_URL. Configuration and credentials are resolved before any
    network activity. Caller-supplied credential headers are discarded.
    """
    try:
        resolved_base = resolve_axis_base_url(base_url)
        url = build_axis_url(resolved_base, endpoint_path)
    except AxisConfigError as exc:
        return _finish(KIND_NOT_CONFIGURED, reason=exc.reason)

    is_execute = method.upper() == "POST" and endpoint_path == EXECUTE_ENDPOINT
    secure = _is_secure_transport(resolved_base)
    if is_execute and not secure:
        return _finish(KIND_INSECURE_TRANSPORT)

    bypass_secret, bypass_valid = _bypass_secret()
    if not bypass_valid:
        return _finish(KIND_BYPASS_INVALID)

    token = None
    if is_execute:
        token = _service_token()
        if token is None:
            return _finish(KIND_AUTH_NOT_CONFIGURED)

    request_headers = {key: value for key, value in headers.items() if key.lower() not in _CREDENTIAL_HEADERS}
    if secure:
        if token is not None:
            request_headers[AUTHORIZATION_HEADER] = f"Bearer {token}"
        if bypass_secret is not None:
            request_headers[VERCEL_BYPASS_HEADER] = bypass_secret

    kwargs: dict[str, Any] = {
        "headers": request_headers,
        "timeout": timeout,
        "allow_redirects": False,
    }
    if json_body is not None:
        kwargs["json"] = json_body

    try:
        response = requests.request(method, url, **kwargs)
    except requests.Timeout:
        return _finish(KIND_TIMEOUT)
    except requests.RequestException:
        return _finish(KIND_CONNECTION_ERROR)

    status = response.status_code
    if 300 <= status < 400:
        return _finish(KIND_REDIRECT, status)
    if not 200 <= status < 300:
        return _finish(KIND_HTTP_ERROR, status)

    try:
        body = response.json()
    except ValueError:
        return _finish(KIND_NON_JSON, status)
    except requests.RequestException:
        return _finish(KIND_CONNECTION_ERROR, status)

    if not isinstance(body, dict):
        return _finish(KIND_NON_JSON, status)
    if body.get("ok") is not True or not isinstance(body.get("data"), dict):
        return _finish(KIND_NOT_OK, status)

    return _finish(KIND_SUCCESS, status, data=body["data"])
