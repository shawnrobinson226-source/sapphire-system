"""Strict HTTP transport for Sapphire -> AXIS requests.

One request per call, redirects never followed, no retries. The outcome is
decided by HTTP status first (3xx -> redirect, >= 400 -> http_error); only a
2xx body is inspected, and it must be a JSON object with top-level ``ok`` True
and an object ``data`` (the AXIS v1 envelope). Endpoint-specific checks (for
example execute's ``data.sessionId``) belong to the caller.

Failures carry only a kind, the HTTP status and, for configuration errors, a
fixed reason code. Response bodies, URLs, hosts, headers and exception text
are never returned or logged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from core.sapphire.axis_config import AxisConfigError, build_axis_url, resolve_axis_base_url

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
    AXIS_BASE_URL. Configuration is resolved before any network activity.
    """
    try:
        url = build_axis_url(resolve_axis_base_url(base_url), endpoint_path)
    except AxisConfigError as exc:
        return _finish(KIND_NOT_CONFIGURED, reason=exc.reason)

    kwargs: dict[str, Any] = {
        "headers": dict(headers),
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
