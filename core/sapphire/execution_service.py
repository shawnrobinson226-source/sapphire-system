"""Sapphire execution surface: validate, delegate to AXIS adapter, normalize response."""

from __future__ import annotations

from typing import Any

from core.sapphire.axis_adapter import AxisAdapter
from core.sapphire.session_service import SessionService
from core.security.violations import log_boundary_violation


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
    def _first_action(axis_data: dict[str, Any]) -> Any:
        if "action" in axis_data:
            return axis_data.get("action")
        steps = axis_data.get("steps")
        if isinstance(steps, list) and steps:
            return steps[0]
        return None

    def _normalize_success(self, axis_data: dict[str, Any], *, status_code: int | None = None) -> dict:
        return {
            "ok": True,
            "axis": {
                "classification": axis_data.get("classification"),
                "protocol": axis_data.get("protocol"),
                "action": self._first_action(axis_data),
                "outcome": axis_data.get("outcome"),
                "continuity": axis_data.get("continuity"),
            },
            "pipeline": {
                "source": "axis_adapter",
                "status_code": status_code,
            },
        }

    def execute(
        self,
        trigger_or_request: str | dict[str, Any],
        operator_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        endpoint_label = "POST /api/v2/execute"
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
                    operator_id=clean_operator_id,
                    payload={"trigger": trigger},
                    details={"field": "trigger"},
                )
                return self._failure(
                    error_type="validation_error",
                    message=str(exc),
                    safe_details={"field": "trigger"},
                )

            request_payload["trigger"] = clean_trigger
            adapter_response = self.axis_adapter.call_axis(
                "POST",
                "/api/v2/execute",
                clean_operator_id,
                payload=request_payload,
            )

            if adapter_response.get("ok"):
                axis_data = adapter_response.get("data")
                if not isinstance(axis_data, dict):
                    axis_data = {}
                if axis_data.get("gated") is True:
                    result = {
                        "ok": True,
                        "gated": True,
                        "gate_type": axis_data.get("gate_type"),
                        "message": axis_data.get("message", ""),
                    }
                else:
                    result = self._normalize_success(
                        axis_data,
                        status_code=adapter_response.get("status_code"),
                    )
                if session_id and self.session_service is not None:
                    try:
                        self.session_service.append_to_session(
                            session_id=session_id,
                            execution_result=result,
                            trigger=clean_trigger,
                            operator_id=clean_operator_id,
                        )
                    except Exception as exc:
                        log_boundary_violation(
                            violation_type="session_error",
                            endpoint=endpoint_label,
                            operator_id=clean_operator_id,
                            payload={"session_id": session_id},
                            details={"exception_type": type(exc).__name__},
                        )
                return result

            if adapter_response.get("error") == "boundary_violation":
                log_boundary_violation(
                    violation_type="boundary_violation",
                    endpoint=adapter_response.get("endpoint") or endpoint_label,
                    operator_id=clean_operator_id,
                    payload=request_payload,
                    details={
                        "violation_type": adapter_response.get("violation_type"),
                        "status_code": adapter_response.get("status_code"),
                    },
                )
                result = self._failure(
                    error_type="boundary_violation",
                    message="Request rejected by AXIS boundary rules.",
                    safe_details={
                        "violation_type": adapter_response.get("violation_type"),
                        "endpoint": adapter_response.get("endpoint"),
                    },
                )
                if session_id and self.session_service is not None:
                    try:
                        self.session_service.append_to_session(
                            session_id=session_id,
                            execution_result=result,
                            trigger=clean_trigger,
                            operator_id=clean_operator_id,
                        )
                    except Exception as exc:
                        log_boundary_violation(
                            violation_type="session_error",
                            endpoint=endpoint_label,
                            operator_id=clean_operator_id,
                            payload={"session_id": session_id},
                            details={"exception_type": type(exc).__name__},
                        )
                return result

            log_boundary_violation(
                violation_type="axis_error",
                endpoint=endpoint_label,
                operator_id=clean_operator_id,
                payload=request_payload,
                details={"status_code": adapter_response.get("status_code")},
            )
            axis_data = adapter_response.get("data")
            status_code = adapter_response.get("status_code")
            message = "AXIS request failed."
            safe_details: dict[str, Any] = {"status_code": status_code}
            if isinstance(axis_data, dict):
                axis_error = axis_data.get("error")
                axis_ok = axis_data.get("ok")
                axis_version = axis_data.get("version")
                if axis_ok is False and isinstance(axis_error, str) and axis_error.strip():
                    message = axis_error.strip()
                    safe_details = {}
                    if isinstance(axis_version, str) and axis_version.strip():
                        safe_details["version"] = axis_version.strip()
            result = self._failure(
                error_type="axis_error",
                message=message,
                safe_details=safe_details,
            )
            if session_id and self.session_service is not None:
                try:
                    self.session_service.append_to_session(
                        session_id=session_id,
                        execution_result=result,
                        trigger=clean_trigger,
                        operator_id=clean_operator_id,
                    )
                except Exception as exc:
                    log_boundary_violation(
                        violation_type="session_error",
                        endpoint=endpoint_label,
                        operator_id=clean_operator_id,
                        payload={"session_id": session_id},
                        details={"exception_type": type(exc).__name__},
                    )
            return result

        except Exception as exc:
            log_boundary_violation(
                violation_type="axis_error",
                endpoint=endpoint_label,
                operator_id=operator_id if isinstance(operator_id, str) and operator_id.strip() else None,
                payload=None,
                details={"exception_type": type(exc).__name__},
            )
            return self._failure(
                error_type="axis_error",
                message="AXIS request failed unexpectedly.",
                safe_details={"exception_type": type(exc).__name__},
            )
