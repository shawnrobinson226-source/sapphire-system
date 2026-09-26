"""
AXIS (VANTA) integration tools for Sapphire.
"""

import logging
import math
from typing import Any, Callable, Dict, Tuple

from core.sapphire import axis_http
from core.sapphire.axis_config import AXIS_NOT_CONFIGURED, AxisConfigError
from core.sapphire.axis_execution_guard import assert_axis_execution_allowed

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = "A"
AVAILABLE_FUNCTIONS = [
    "fetch_axis_analytics",
    "fetch_axis_operator_profile",
]

DEFAULT_TIMEOUT_SECONDS = axis_http.DEFAULT_TIMEOUT_SECONDS

TOOLS = [
    {
        "type": "function",
        "is_local": False,
        "network": True,
        "function": {
            "name": "fetch_axis_analytics",
            "description": "Fetch AXIS analytics data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operator_id": {
                        "type": "string",
                        "description": "Operator ID passed in x-operator-id header.",
                    }
                },
                "required": ["operator_id"],
            },
        },
    },
    {
        "type": "function",
        "is_local": False,
        "network": True,
        "function": {
            "name": "fetch_axis_operator_profile",
            "description": "Fetch AXIS operator profile data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operator_id": {
                        "type": "string",
                        "description": "Operator ID passed in x-operator-id header.",
                    }
                },
                "required": ["operator_id"],
            },
        },
    },
]


def _validate_operator_id(operator_id: str) -> Tuple[Dict[str, Any] | None, bool]:
    if not operator_id or not operator_id.strip():
        return {"error": "A non-empty 'operator_id' is required."}, False
    return None, True


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _request_axis(
    method: str,
    endpoint: str,
    operator_id: str,
    payload: Dict[str, Any] | None = None,
    success_check: Tuple[str, Callable[[Dict[str, Any]], bool]] | None = None,
) -> Tuple[Dict[str, Any], bool]:
    guard_path = f"axis_integration.{method.lower()}_{endpoint}"
    allowed, blocked = assert_axis_execution_allowed(guard_path)
    if not allowed:
        return blocked, False

    operator_validation, ok = _validate_operator_id(operator_id)
    if not ok:
        return operator_validation, False

    headers = {"x-operator-id": operator_id}
    if payload is not None:
        headers["Content-Type"] = "application/json"

    result = axis_http.request_axis(
        method,
        f"/api/v2/{endpoint}",
        headers=headers,
        json_body=payload,
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    if not result.ok:
        return _failure(endpoint, result), False
    if success_check is not None:
        failure_kind, check = success_check
        if not check(result.data):
            logger.warning("[AXIS_HTTP] request failed kind=%s status=%s", failure_kind, result.status)
            return {"endpoint": endpoint, "status_code": result.status, "error": failure_kind}, False
    return result.data, True


def _failure(endpoint: str, result: axis_http.AxisResult) -> Dict[str, Any]:
    """Controlled failure: kind, HTTP status and (config only) a fixed reason."""
    if result.kind == axis_http.KIND_NOT_CONFIGURED:
        return {
            "endpoint": endpoint,
            "status_code": None,
            "error": AXIS_NOT_CONFIGURED,
            "reason": result.reason,
            "message": str(AxisConfigError(result.reason)),
        }
    return {"endpoint": endpoint, "status_code": result.status, "error": result.kind}


def _execute_axis(
    trigger: Any,
    operator_id: str,
    classification: Any,
    next_action: Any,
    stability: Any = None,
    reference: Any = None,
    impact: Any = None,
) -> Tuple[Dict[str, Any], bool]:
    if not isinstance(trigger, str) or not trigger.strip():
        return {"error": "A non-empty 'trigger' is required."}, False
    if not isinstance(classification, str) or not classification.strip():
        return {"error": "A non-empty 'classification' is required."}, False
    if not isinstance(next_action, str) or not next_action.strip():
        return {"error": "A non-empty 'next_action' is required."}, False
    if stability is not None and not _is_number(stability):
        return {"error": "'stability' must be a number when provided."}, False
    if reference is not None and not isinstance(reference, bool):
        return {"error": "'reference' must be a boolean when provided."}, False
    if impact is not None and not _is_number(impact):
        return {"error": "'impact' must be a number when provided."}, False
    payload = {
        "trigger": trigger.strip(),
        "classification": classification.strip(),
        "next_action": next_action.strip(),
    }
    if stability is not None:
        payload["stability"] = stability
    if reference is not None:
        payload["reference"] = reference
    if impact is not None:
        payload["impact"] = impact
    return _request_axis(
        "POST", "execute", operator_id, payload,
        success_check=("missing_session_id", has_execute_session_id),
    )


def has_execute_session_id(data: Any) -> bool:
    """Execute success rule: a verified execution returns a non-empty data.sessionId."""
    session_id = data.get("sessionId") if isinstance(data, dict) else None
    return isinstance(session_id, str) and bool(session_id.strip())


def _fetch_axis_analytics(operator_id: str) -> Tuple[Dict[str, Any], bool]:
    return _request_axis("GET", "analytics", operator_id)


def _fetch_axis_operator_profile(operator_id: str) -> Tuple[Dict[str, Any], bool]:
    return _request_axis("GET", "operator-profile", operator_id)


def execute(function_name, arguments, config, plugin_settings=None):
    arguments = arguments or {}

    if function_name == "execute_axis":
        return _execute_axis(
            trigger=arguments.get("trigger", ""),
            operator_id=arguments.get("operator_id", ""),
            classification=arguments.get("classification", ""),
            next_action=arguments.get("next_action", ""),
            stability=arguments.get("stability"),
            reference=arguments.get("reference"),
            impact=arguments.get("impact"),
        )

    if function_name == "fetch_axis_analytics":
        return _fetch_axis_analytics(operator_id=arguments.get("operator_id", ""))

    if function_name == "fetch_axis_operator_profile":
        return _fetch_axis_operator_profile(operator_id=arguments.get("operator_id", ""))

    return {"error": f"Unknown function '{function_name}'."}, False
