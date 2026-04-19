"""
AXIS (VANTA) integration tools for Sapphire.
"""

import logging
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
                    "distortion_class": {
                        "type": "string",
                        "description": "AXIS distortion class value.",
                    },
                    "next_action": {
                        "type": "string",
                        "description": "AXIS next action value.",
                    },
                    "operator_id": {
                        "type": "string",
                        "description": "Operator ID passed in x-operator-id header.",
                    },
                },
                "required": ["trigger", "distortion_class", "next_action", "operator_id"],
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
    trigger: str,
    operator_id: str,
    distortion_class: str,
    next_action: str,
) -> Tuple[Dict[str, Any], bool]:
    if not trigger or not trigger.strip():
        return {"error": "A non-empty 'trigger' is required."}, False
    if not distortion_class or not distortion_class.strip():
        return {"error": "A non-empty 'distortion_class' is required."}, False
    if not next_action or not next_action.strip():
        return {"error": "A non-empty 'next_action' is required."}, False
    payload = {
        "trigger": trigger.strip(),
        "distortion_class": distortion_class.strip(),
        "next_action": next_action.strip(),
    }
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
            distortion_class=arguments.get("distortion_class", ""),
            next_action=arguments.get("next_action", ""),
        )

    if function_name == "fetch_axis_analytics":
        return _fetch_axis_analytics(operator_id=arguments.get("operator_id", ""))

    if function_name == "fetch_axis_operator_profile":
        return _fetch_axis_operator_profile(operator_id=arguments.get("operator_id", ""))

    return {"error": f"Unknown function '{function_name}'."}, False
