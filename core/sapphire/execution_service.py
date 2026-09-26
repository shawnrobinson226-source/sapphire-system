"""Sapphire execution surface: validate, delegate to AXIS adapter, normalize response.

Execution succeeds only on a verified adapter success: the transport verified
the AXIS v1 envelope and the execute rule verified a non-empty data.sessionId.
The success result copies only named contract fields. Failures carry a fixed
message plus a controlled kind and HTTP status; no AXIS-supplied text,
exception text, operator ID or caller-supplied field name is returned,
stored in a session entry, or written to the boundary log.
"""

from __future__ import annotations

from typing import Any

from core.sapphire import axis_http
from core.sapphire.axis_adapter import (
    ALLOWED_ENDPOINTS,
    KIND_MISSING_SESSION_ID,
    AxisAdapter,
    payload_summary,
    safe_status,
)
from core.sapphire.axis_config import AXIS_NOT_CONFIGURED, AxisConfigError
from core.sapphire.axis_contract import (
    AXIS_EXECUTE_FIELDS,
    EXECUTE_DATA_FIELDS,
    EXECUTE_ENDPOINT,
    has_execute_session_id,
)
from core.sapphire.session_service import SessionService
from core.security.violations import log_boundary_violation

__all__ = ["AXIS_EXECUTE_FIELDS", "ExecutionService"]

AXIS_FAILURE_MESSAGE = "AXIS request failed."
AXIS_UNEXPECTED_MESSAGE = "AXIS request failed unexpectedly."
BOUNDARY_MESSAGE = "Request rejected by AXIS boundary rules."

REMOTE_FAILURE_KINDS = frozenset({
    axis_http.KIND_REDIRECT,
    axis_http.KIND_HTTP_ERROR,
    axis_http.KIND_TIMEOUT,
    axis_http.KIND_CONNECTION_ERROR,
    axis_http.KIND_NON_JSON,
    axis_http.KIND_NOT_OK,
    axis_http.KIND_AUTH_NOT_CONFIGURED,
    axis_http.KIND_BYPASS_INVALID,
    axis_http.KIND_INSECURE_TRANSPORT,
    KIND_MISSING_SESSION_ID,
})

BOUNDARY_VIOLATION_TYPES = frozenset({
    "zero_tools_mode",
    "forbidden_endpoint",
    "invalid_operator_id",
    "invalid_payload",
    "invalid_distortion_class",
})

ALLOWED_ENDPOINT_LABELS = frozenset(f"{method} {path}" for method, path in ALLOWED_ENDPOINTS)


class ExecutionService:
    """Thin orchestration layer over AxisAdapter with a stable public response shape."""

    def __init__(self, axis_adapter: AxisAdapter, session_service: SessionService | None = None):
        self.axis_adapter = axis_adapter
        self.session_service = session_service

    @staticmethod
    def _clean_non_empty(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required.")
        return value.strip()

    @staticmethod
    def _failure(error_type: str, message: str, safe_details: dict[str, Any] | None = None) -> dict:
        return {
            "ok": False,
            "error_type": error_type,
            "message": message,
            "safe_details": safe_details or {},
        }

    @staticmethod
    def _unknown_axis_fields(payload: dict[str, Any]) -> list[Any]:
        return [key for key in payload if key not in AXIS_EXECUTE_FIELDS]

    @staticmethod
    def _verified_success(adapter_response: dict[str, Any]) -> dict | None:
        """Success result from a verified adapter response, else None.

        Re-applies the execute rule so a success is never built from
        unverified data. Only sessionId's type is verified; the other named
        contract fields are copied as-is when present.
        """
        if adapter_response.get("ok") is not True:
            return None
        data = adapter_response.get("data")
        if not has_execute_session_id(data):
            return None
        axis = {"session_id": data["sessionId"].strip()}
        for field in EXECUTE_DATA_FIELDS:
            if field != "sessionId" and field in data:
                axis[field] = data[field]
        return {
            "ok": True,
            "axis": axis,
            "pipeline": {
                "source": "axis_adapter",
                "status_code": safe_status(adapter_response.get("status_code")),
            },
        }

    def _append(self, session_id: str | None, result: dict, trigger: str, operator_id: str) -> None:
        if not session_id or self.session_service is None:
            return
        try:
            self.session_service.append_to_session(
                session_id=session_id,
                execution_result=result,
                trigger=trigger,
                operator_id=operator_id,
            )
        except Exception as exc:
            log_boundary_violation(
                violation_type="session_error",
                endpoint=f"POST {EXECUTE_ENDPOINT}",
                operator_id=None,
                payload=None,
                details={"exception_type": type(exc).__name__},
            )

    def _failure_from_adapter(self, adapter_response: Any, request_payload: dict[str, Any]) -> dict:
        endpoint_label = f"POST {EXECUTE_ENDPOINT}"
        response = adapter_response if isinstance(adapter_response, dict) else {}
        error = response.get("error")

        if error == "boundary_violation":
            violation_type = response.get("violation_type")
            violation_type = violation_type if violation_type in BOUNDARY_VIOLATION_TYPES else None
            endpoint = response.get("endpoint")
            endpoint = endpoint if endpoint in ALLOWED_ENDPOINT_LABELS else None
            log_boundary_violation(
                violation_type="boundary_violation",
                endpoint=endpoint_label,
                operator_id=None,
                payload=payload_summary(request_payload),
                details={"violation_type": violation_type},
            )
            return self._failure(
                error_type="boundary_violation",
                message=BOUNDARY_MESSAGE,
                safe_details={"violation_type": violation_type, "endpoint": endpoint},
            )

        if error == AXIS_NOT_CONFIGURED:
            try:
                config_error = AxisConfigError(response.get("reason"))
                reason, message = config_error.reason, str(config_error)
            except (KeyError, TypeError):
                reason, message = None, "AXIS base URL is not configured."
            log_boundary_violation(
                violation_type=AXIS_NOT_CONFIGURED,
                endpoint=endpoint_label,
                operator_id=None,
                payload=None,
                details={"reason": reason},
            )
            return self._failure(
                error_type=AXIS_NOT_CONFIGURED,
                message=message,
                safe_details={"reason": reason},
            )

        if response.get("ok") is True:
            # Adapter claimed success but the execute rule does not hold.
            kind = KIND_MISSING_SESSION_ID
        else:
            kind = error if error in REMOTE_FAILURE_KINDS else None
        status_code = safe_status(response.get("status_code"))
        log_boundary_violation(
            violation_type="axis_error",
            endpoint=endpoint_label,
            operator_id=None,
            payload=payload_summary(request_payload),
            details={"kind": kind, "status_code": status_code},
        )
        return self._failure(
            error_type="axis_error",
            message=AXIS_FAILURE_MESSAGE,
            safe_details={"kind": kind, "status_code": status_code},
        )

    def execute(
        self,
        trigger_or_request: str | dict[str, Any],
        operator_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        endpoint_label = f"POST {EXECUTE_ENDPOINT}"
        try:
            if isinstance(trigger_or_request, dict):
                request_payload = dict(trigger_or_request)
                effective_operator_id = operator_id if operator_id is not None else request_payload.get("operator_id")
                trigger = request_payload.get("trigger")
                request_payload.pop("operator_id", None)
            else:
                request_payload = {"trigger": trigger_or_request}
                effective_operator_id = operator_id
                trigger = trigger_or_request

            try:
                clean_operator_id = self._clean_non_empty(effective_operator_id, "operator_id")
            except ValueError as exc:
                log_boundary_violation(
                    violation_type="validation_error",
                    endpoint=endpoint_label,
                    operator_id=None,
                    payload={"operator_id": effective_operator_id, "trigger": trigger},
                    details={"field": "operator_id"},
                )
                return self._failure(
                    error_type="validation_error",
                    message=str(exc),
                    safe_details={"field": "operator_id"},
                )

            try:
                clean_trigger = self._clean_non_empty(trigger, "trigger")
            except ValueError as exc:
                log_boundary_violation(
                    violation_type="validation_error",
                    endpoint=endpoint_label,
                    operator_id=None,
                    payload={"trigger": trigger},
                    details={"field": "trigger"},
                )
                return self._failure(
                    error_type="validation_error",
                    message=str(exc),
                    safe_details={"field": "trigger"},
                )

            request_payload["trigger"] = clean_trigger
            unknown_fields = self._unknown_axis_fields(request_payload)
            if unknown_fields:
                log_boundary_violation(
                    violation_type="validation_error",
                    endpoint=endpoint_label,
                    operator_id=None,
                    payload={"unknown_field_count": len(unknown_fields)},
                    details={"field": "axis_payload"},
                )
                return self._failure(
                    error_type="validation_error",
                    message="Request contains fields outside the AXIS contract.",
                    safe_details={"field": "axis_payload", "unknown_field_count": len(unknown_fields)},
                )

            adapter_response = self.axis_adapter.call_axis(
                "POST",
                EXECUTE_ENDPOINT,
                clean_operator_id,
                payload=request_payload,
            )

            result = None
            if isinstance(adapter_response, dict):
                result = self._verified_success(adapter_response)
            if result is None:
                result = self._failure_from_adapter(adapter_response, request_payload)
            self._append(session_id, result, clean_trigger, clean_operator_id)
            return result

        except Exception as exc:
            log_boundary_violation(
                violation_type="axis_error",
                endpoint=endpoint_label,
                operator_id=None,
                payload=None,
                details={"exception_type": type(exc).__name__},
            )
            return self._failure(
                error_type="axis_error",
                message=AXIS_UNEXPECTED_MESSAGE,
                safe_details={"exception_type": type(exc).__name__},
            )
