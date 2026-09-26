"""Sapphire renderer for AXIS-aligned execution responses."""

from __future__ import annotations

import math
from typing import Any

from core.sapphire.axis_adapter import safe_status
from core.sapphire.execution_service import REMOTE_FAILURE_KINDS


def _to_text(value: Any, default: str = "N/A") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        clean = value.strip()
        return clean if clean else default
    return str(value)


def _protocol_steps(axis: dict[str, Any]) -> list[str]:
    protocol = axis.get("protocol")
    if isinstance(protocol, dict):
        steps = protocol.get("steps")
        if isinstance(steps, list):
            return [str(step) for step in steps]
        return [str(protocol)]
    if isinstance(protocol, list):
        return [str(step) for step in protocol]
    if protocol is None:
        return []
    return [str(protocol)]


# Contract fields rendered for a verified execution, in display order.
_CONTRACT_DISPLAY_FIELDS = (
    ("Session", "session_id"),
    ("Outcome", "outcome"),
    ("Clarity Rating", "clarity_rating"),
    ("Steps Completed", "steps_completed"),
    ("Continuity Before", "continuity_before"),
    ("Continuity After", "continuity_after"),
    ("Protocol Output", "protocol_output"),
)

LEGACY_PAUSE_MESSAGE = "Legacy pause entry. Stored message is not displayed."


def _scalar_text(value: Any) -> str:
    """Display only strings and finite numbers; anything else is N/A.

    Contract fields other than sessionId are not type-verified, so objects
    are never stringified for display.
    """
    if isinstance(value, bool):
        return "N/A"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value) if math.isfinite(value) else "N/A"
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "N/A"


def _render_contract_success(axis: dict[str, Any]) -> str:
    lines = ["=== AXIS RESULT ==="]
    for label, key in _CONTRACT_DISPLAY_FIELDS:
        lines.append(f"{label}: {_scalar_text(axis.get(key))}")
    return "\n".join(lines)


def render_success(response: dict[str, Any]) -> str:
    axis = response.get("axis")
    if not isinstance(axis, dict):
        axis = {}

    # A verified S2+ result carries session_id; older stored entries use the
    # legacy classification/protocol/action/continuity layout.
    if "session_id" in axis:
        return _render_contract_success(axis)

    lines = [
        "=== AXIS RESULT ===",
        f"Classification: {_to_text(axis.get('classification'))}",
        "",
        "Protocol:",
    ]

    steps = _protocol_steps(axis)
    if steps:
        for idx, step in enumerate(steps, start=1):
            lines.append(f"{idx}. {step}")
    else:
        lines.append("1. N/A")

    lines.extend(
        [
            "",
            "Action:",
            _to_text(axis.get("action")),
            "",
            "Outcome:",
            _to_text(axis.get("outcome")),
            "",
            "Continuity:",
            _to_text(axis.get("continuity")),
        ]
    )
    return "\n".join(lines)


def render_gated(response: dict[str, Any]) -> str:
    # Gated results are no longer produced (a response without a verified
    # sessionId is a failure). Legacy gated entries may hold AXIS-supplied
    # free text, so their stored message is never re-displayed.
    return f"=== SYSTEM PAUSE === {LEGACY_PAUSE_MESSAGE}"


# Fixed failure text per error type. A stored or supplied message is never
# displayed: legacy entries may hold AXIS-supplied or exception text.
_FAILURE_MESSAGES = {
    "validation_error": "Request failed validation.",
    "boundary_violation": "Request rejected by AXIS boundary rules.",
    "axis_not_configured": "AXIS is not configured.",
    "axis_error": "AXIS request failed.",
}
_GENERIC_FAILURE_MESSAGE = "Execution failed."


def render_failure(response: dict[str, Any]) -> str:
    error_type = response.get("error_type")
    known = isinstance(error_type, str) and error_type in _FAILURE_MESSAGES
    lines = [
        "=== EXECUTION FAILURE ===",
        f"Type: {error_type if known else 'unknown'}",
        f"Message: {_FAILURE_MESSAGES[error_type] if known else _GENERIC_FAILURE_MESSAGE}",
    ]
    details = response.get("safe_details")
    if isinstance(details, dict):
        kind = details.get("kind")
        if isinstance(kind, str) and kind in REMOTE_FAILURE_KINDS:
            lines.append(f"Kind: {kind}")
        status = safe_status(details.get("status_code"))
        if status is not None:
            lines.append(f"Status: {status}")
    return "\n".join(lines)
