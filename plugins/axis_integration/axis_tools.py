"""
AXIS (VANTA) integration tools for Sapphire.
"""

import logging
import math
from typing import Any, Dict, Tuple

import requests

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = "A"
AVAILABLE_FUNCTIONS = [
    "execute_axis",
    "fetch_axis_analytics",
    "fetch_axis_operator_profile",
]

BASE_URL = "https://vanta-app-gilt.vercel.app/api/v2"
DEFAULT_TIMEOUT_SECONDS = 20

TOOLS = [
    {
        "type": "function",
        "is_local": False,
        "network": True,
        "function": {
            "name": "execute_axis",
            "description": "Execute an AXIS trigger for a specific operator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trigger": {
                        "type": "string",
                        "description": "AXIS trigger name or payload string.",
                    },
                    "classification": {
                        "type": "string",
                        "description": "AXIS classification value.",
                    },
                    "next_action": {
                        "type": "string",
                        "description": "AXIS next action value.",
                    },
                    "stability": {
                        "type": "number",
                        "description": "Optional AXIS guard stability value.",
                    },
                    "reference": {
                        "type": "boolean",
                        "description": "Optional AXIS guard reference value.",
                    },
                    "impact": {
                        "type": "number",
                        "description": "Optional AXIS guard impact value.",
                    },
                    "operator_id": {
                        "type": "string",
                        "description": "Operator ID passed in x-operator-id header.",
                    },
                },
                "required": ["trigger", "classification", "next_action", "operator_id"],
            },
        },
    },
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


def _safe_json_response(response: requests.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {
            "status_code": response.status_code,
            "text": response.text,
        }


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
) -> Tuple[Dict[str, Any], bool]:
    operator_validation, ok = _validate_operator_id(operator_id)
    if not ok:
        return operator_validation, False

    url = f"{BASE_URL}/{endpoint}"
    headers = {"x-operator-id": operator_id}

    request_kwargs: Dict[str, Any] = {
        "headers": headers,
        "timeout": DEFAULT_TIMEOUT_SECONDS,
    }

    if payload is not None:
        headers["Content-Type"] = "application/json"
        request_kwargs["json"] = payload

    request_fn = requests.post if method == "POST" else requests.get
    try:
        response = request_fn(url, **request_kwargs)
        if 200 <= response.status_code < 300:
            return _safe_json_response(response), True
        return {
            "endpoint": endpoint,
            "status_code": response.status_code,
            "response_text": response.text or "",
        }, False
    except requests.RequestException as error:
        logger.error("AXIS request failed for endpoint '%s': %s", endpoint, error, exc_info=True)
        return {
            "endpoint": endpoint,
            "status_code": None,
            "response_text": str(error),
        }, False


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
    return _request_axis("POST", "execute", operator_id, payload)


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
