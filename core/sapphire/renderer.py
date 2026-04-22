"""Sapphire renderer for AXIS-aligned execution responses."""

from __future__ import annotations

from typing import Any


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


def render_success(response: dict[str, Any]) -> str:
    axis = response.get("axis")
    if not isinstance(axis, dict):
        axis = {}

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
    message = _to_text(response.get("message"), default="")
    return f"=== SYSTEM PAUSE === {message}"


def render_failure(response: dict[str, Any]) -> str:
    return "\n".join(
        [
            "=== EXECUTION FAILURE ===",
            f"Type: {_to_text(response.get('error_type'))}",
            f"Message: {_to_text(response.get('message'))}",
        ]
    )
