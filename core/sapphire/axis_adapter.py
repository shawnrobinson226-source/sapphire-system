"""Sapphire AXIS adapter: strict boundary + request mediation only.

Every request goes through core.sapphire.axis_http.request_axis (one request,
redirects never followed, status first, v1 envelope). Execute additionally
requires a non-empty data.sessionId (core.sapphire.axis_contract).

Results are plain dicts:
- success: {"ok": True, "status_code": int, "data": dict}
- remote failure: {"ok": False, "error": <transport kind>, "status_code": int 100-599 | None}
- not configured: {"ok": False, "error": AXIS_NOT_CONFIGURED, "status_code": None,
  "reason": <fixed code>, "message": <fixed text>}
- local boundary rejection: {"ok": False, "error": "boundary_violation",
  "status_code": None, "violation_type": <fixed code>, "message": <fixed text>,
  "endpoint": <allowlisted label> | None}

No response text, URL, host, headers, exception text, AXIS error message,
operator ID, payload value or caller-supplied field name is ever returned or
logged.
"""

from __future__ import annotations

from typing import Any

from core.sapphire import axis_http
from core.sapphire.axis_config import AXIS_NOT_CONFIGURED, AxisConfigError
from core.sapphire.axis_contract import (
    AXIS_EXECUTE_FIELDS,
    EXECUTE_ENDPOINT,
    has_execute_session_id,
)
from core.sapphire.axis_execution_guard import assert_axis_execution_allowed
from core.sapphire.distortion_lock import ALLOWED_DISTORTION_CLASSES
from core.security.violations import log_boundary_violation

ALLOWED_ENDPOINTS = {
    ("POST", EXECUTE_ENDPOINT),
    ("GET", "/api/v2/analytics"),
    ("GET", "/api/v2/operator-profile"),
}

KIND_MISSING_SESSION_ID = "missing_session_id"

FORBIDDEN_ENDPOINT_LABEL = "forbidden_endpoint"

_BOUNDARY_MESSAGES = {
    "zero_tools_mode": "AXIS execution blocked because Zero tools mode is active.",
    "forbidden_endpoint": "Endpoint not allowed.",
    "invalid_operator_id": "operator_id must be a non-empty string.",
    "invalid_payload": "Request contains fields outside the AXIS contract.",
    "invalid_distortion_class": "classification is not allowed by Sapphire lock.",
}


def safe_status(value: Any) -> int | None:
    """Return an HTTP status only when it is an int in 100-599."""
    if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
        return value
    return None


def payload_summary(payload: Any) -> dict | None:
    """Log-safe payload description: allowlisted field names + a count of the rest.

    Caller-supplied keys outside AXIS_EXECUTE_FIELDS are never recorded, since
    a key can itself carry a secret. Values are reduced to shapes by the
    violation logger.
    """
    if payload is None:
        return None
    if not isinstance(payload, dict):
        return {"payload_type": "non_dict"}
    known = {key: payload[key] for key in payload if isinstance(key, str) and key in AXIS_EXECUTE_FIELDS}
    return {"fields": known, "unknown_field_count": len(payload) - len(known)}


class AxisAdapter:
    """Strict AXIS transport wrapper with endpoint allowlist enforcement."""

    def __init__(self, axis_base_url: str | None = None, timeout_seconds: int = 20):
        # Not validated here: an explicit value (e.g. the CLI flag) or, when
        # None, AXIS_BASE_URL is resolved at the request boundary so that
        # constructing the adapter never requires AXIS configuration.
        self._axis_base_url = axis_base_url
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _normalize(method: str, endpoint: str) -> tuple[str, str]:
        clean_method = method.upper().strip() if isinstance(method, str) else ""
        endpoint = endpoint if isinstance(endpoint, str) else ""
        clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return clean_method, clean_endpoint

    @staticmethod
    def _require_non_empty_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _boundary_failure(violation_type: str, endpoint: str | None) -> dict:
        return {
            "ok": False,
            "status_code": None,
            "error": "boundary_violation",
            "violation_type": violation_type,
            "message": _BOUNDARY_MESSAGES[violation_type],
            "endpoint": endpoint,
        }

    @staticmethod
    def _remote_failure(kind: str, status: Any) -> dict:
        return {"ok": False, "status_code": safe_status(status), "error": kind}

    def call_axis(
        self,
        method: str,
        endpoint: str,
        operator_id: str,
        payload: dict | None = None,
    ) -> dict:
        clean_method, clean_endpoint = self._normalize(method, endpoint)
        allowed_endpoint = (clean_method, clean_endpoint) in ALLOWED_ENDPOINTS
        # Only an allowlisted endpoint is ever echoed, as a fixed label.
        endpoint_label = f"{clean_method} {clean_endpoint}" if allowed_endpoint else None

        allowed, _blocked = assert_axis_execution_allowed(
            f"axis_adapter.{endpoint_label or FORBIDDEN_ENDPOINT_LABEL}"
        )
        if not allowed:
            return self._boundary_failure("zero_tools_mode", endpoint_label)

        if not allowed_endpoint:
            log_boundary_violation(
                violation_type="forbidden_endpoint",
                endpoint=FORBIDDEN_ENDPOINT_LABEL,
                operator_id=None,
                payload=None,
            )
            return self._boundary_failure("forbidden_endpoint", None)

        try:
            clean_operator_id = self._require_non_empty_string(operator_id, "operator_id")
        except ValueError:
            log_boundary_violation(
                violation_type="invalid_operator_id",
                endpoint=endpoint_label,
                operator_id=None,
                payload=payload_summary(payload),
            )
            return self._boundary_failure("invalid_operator_id", endpoint_label)

        is_execute = clean_endpoint == EXECUTE_ENDPOINT
        payload_ok = (
            isinstance(payload, dict) and all(isinstance(k, str) and k in AXIS_EXECUTE_FIELDS for k in payload)
            if is_execute
            else payload is None
        )
        if not payload_ok:
            log_boundary_violation(
                violation_type="invalid_payload",
                endpoint=endpoint_label,
                operator_id=None,
                payload=payload_summary(payload),
            )
            return self._boundary_failure("invalid_payload", endpoint_label)

        headers = {"x-operator-id": clean_operator_id}
        if payload is not None:
            headers["Content-Type"] = "application/json"

        result = axis_http.request_axis(
            clean_method,
            clean_endpoint,
            headers=headers,
            json_body=payload,
            base_url=self._axis_base_url,
            timeout=self.timeout_seconds,
        )

        if result.kind == axis_http.KIND_NOT_CONFIGURED:
            return {
                "ok": False,
                "status_code": None,
                "error": AXIS_NOT_CONFIGURED,
                "reason": result.reason,
                "message": str(AxisConfigError(result.reason)),
                "endpoint": endpoint_label,
            }
        if not result.ok:
            return self._remote_failure(result.kind, result.status)
        if is_execute and not has_execute_session_id(result.data):
            return self._remote_failure(KIND_MISSING_SESSION_ID, result.status)
        status = safe_status(result.status)
        if status is None or not isinstance(result.data, dict):
            return self._remote_failure(axis_http.KIND_NOT_OK, None)
        return {"ok": True, "status_code": status, "data": result.data}

    def execute(
        self,
        trigger: str,
        classification: str,
        next_action: str,
        operator_id: str,
        stability: float | None = None,
        reference: bool | None = None,
        impact: float | None = None,
    ) -> dict:
        clean_trigger = self._require_non_empty_string(trigger, "trigger")
        clean_classification = self._require_non_empty_string(classification, "classification")
        clean_next_action = self._require_non_empty_string(next_action, "next_action")

        endpoint_label = f"POST {EXECUTE_ENDPOINT}"
        if clean_classification not in ALLOWED_DISTORTION_CLASSES:
            log_boundary_violation(
                violation_type="invalid_distortion_class",
                endpoint=endpoint_label,
                operator_id=None,
                payload={"classification": clean_classification},
            )
            return self._boundary_failure("invalid_distortion_class", endpoint_label)

        payload = {
            "trigger": clean_trigger,
            "classification": clean_classification,
            "next_action": clean_next_action,
        }
        if stability is not None:
            payload["stability"] = stability
        if reference is not None:
            payload["reference"] = reference
        if impact is not None:
            payload["impact"] = impact
        return self.call_axis("POST", EXECUTE_ENDPOINT, operator_id, payload=payload)

    def fetch_analytics(self, operator_id: str) -> dict:
        return self.call_axis("GET", "/api/v2/analytics", operator_id)

    def fetch_operator_profile(self, operator_id: str) -> dict:
        return self.call_axis("GET", "/api/v2/operator-profile", operator_id)
