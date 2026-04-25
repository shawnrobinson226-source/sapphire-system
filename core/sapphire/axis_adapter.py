"""Sapphire AXIS adapter: strict boundary + request mediation only."""

from __future__ import annotations

from typing import Any

import requests

from core.sapphire.distortion_lock import ALLOWED_DISTORTION_CLASSES
from core.security.violations import log_boundary_violation

ALLOWED_ENDPOINTS = {
    ("POST", "/api/v2/execute"),
    ("GET", "/api/v2/analytics"),
    ("GET", "/api/v2/operator-profile"),
}


class AxisAdapter:
    """Strict AXIS transport wrapper with endpoint allowlist enforcement."""

    def __init__(self, axis_base_url: str, timeout_seconds: int = 20):
        self.axis_base_url = axis_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _normalize(method: str, endpoint: str) -> tuple[str, str]:
        clean_method = (method or "").upper().strip()
        clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return clean_method, clean_endpoint

    @staticmethod
    def _require_non_empty_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    def _enforce_allowed_endpoint(self, method: str, endpoint: str) -> tuple[str, str]:
        clean_method, clean_endpoint = self._normalize(method, endpoint)
        if (clean_method, clean_endpoint) not in ALLOWED_ENDPOINTS:
            log_boundary_violation(
                violation_type="forbidden_endpoint",
                endpoint=f"{clean_method} {clean_endpoint}",
                operator_id=None,
                payload=None,
            )
            raise ValueError(f"Endpoint not allowed: {clean_method} {clean_endpoint}")
        return clean_method, clean_endpoint

    @staticmethod
    def _boundary_failure(
        violation_type: str,
        endpoint: str,
        message: str,
        operator_id: str | None = None,
        payload: dict | None = None,
    ) -> dict:
        return {
            "ok": False,
            "status_code": 0,
            "error": "boundary_violation",
            "violation_type": violation_type,
            "message": message,
            "endpoint": endpoint,
            "operator_id": operator_id,
            "payload_snapshot": payload or None,
        }

    @staticmethod
    def _parse_response(response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text}
        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "data": data,
        }

    def call_axis(
        self,
        method: str,
        endpoint: str,
        operator_id: str,
        payload: dict | None = None,
    ) -> dict:
        try:
            clean_method, clean_endpoint = self._enforce_allowed_endpoint(method, endpoint)
        except ValueError as exc:
            clean_method, clean_endpoint = self._normalize(method, endpoint)
            return self._boundary_failure(
                violation_type="forbidden_endpoint",
                endpoint=f"{clean_method} {clean_endpoint}",
                message=str(exc),
                operator_id=None,
            )

        try:
            clean_operator_id = self._require_non_empty_string(operator_id, "operator_id")
        except ValueError as exc:
            endpoint_label = f"{clean_method} {clean_endpoint}"
            log_boundary_violation(
                violation_type="invalid_operator_id",
                endpoint=endpoint_label,
                operator_id=None,
                payload=payload,
            )
            return self._boundary_failure(
                violation_type="invalid_operator_id",
                endpoint=endpoint_label,
                message=str(exc),
                operator_id=None,
            )

        url = f"{self.axis_base_url}{clean_endpoint}"
        headers = {"x-operator-id": clean_operator_id}
        kwargs = {"headers": headers, "timeout": self.timeout_seconds}

        if payload is not None:
            kwargs["json"] = payload
            headers["Content-Type"] = "application/json"

        response = requests.request(clean_method, url, **kwargs)
        return self._parse_response(response)

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

        if clean_classification not in ALLOWED_DISTORTION_CLASSES:
            log_boundary_violation(
                violation_type="invalid_distortion_class",
                endpoint="POST /api/v2/execute",
                operator_id=operator_id if isinstance(operator_id, str) and operator_id.strip() else None,
                payload={"classification": clean_classification},
            )
            return self._boundary_failure(
                violation_type="invalid_distortion_class",
                endpoint="POST /api/v2/execute",
                message="classification is not allowed by Sapphire lock.",
                operator_id=operator_id if isinstance(operator_id, str) and operator_id.strip() else None,
            )

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
        return self.call_axis("POST", "/api/v2/execute", operator_id, payload=payload)

    def fetch_analytics(self, operator_id: str) -> dict:
        return self.call_axis("GET", "/api/v2/analytics", operator_id)

    def fetch_operator_profile(self, operator_id: str) -> dict:
        return self.call_axis("GET", "/api/v2/operator-profile", operator_id)
