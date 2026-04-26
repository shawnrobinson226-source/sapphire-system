"""View helpers for strict renderer-based UI output."""

from __future__ import annotations

from typing import Any

from core.sapphire.renderer import render_failure, render_gated, render_success


def render_result(response: dict[str, Any] | None) -> str:
    if not response:
        return ""
    if response.get("gated"):
        return render_gated(response)
    if response.get("ok"):
        return render_success(response)
    return render_failure(response)


def render_history_entry(entry: dict[str, Any]) -> str:
    timestamp = entry.get("timestamp", "")
    header = f"--- Entry [{timestamp}] ---"
    result_type = entry.get("result_type")

    if result_type == "gated":
        body = render_gated(
            {
                "ok": True,
                "gated": True,
                "gate_type": (entry.get("gated") or {}).get("gate_type"),
                "message": (entry.get("gated") or {}).get("message", ""),
            }
        )
    elif result_type == "success":
        body = render_success({"ok": True, "axis": entry.get("axis", {})})
    else:
        failure = entry.get("failure") or {}
        body = render_failure(
            {
                "ok": False,
                "error_type": failure.get("error_type"),
                "message": failure.get("message"),
            }
        )
    return f"{header}\n{body}"


def render_tri_state(state: dict[str, Any] | None) -> str:
    if not state:
        return ""

    state_type = state.get("type")
    data = state.get("data") or {}

    if state_type == "idle":
        return "Tri-System Flow\nIdle"

    if state_type == "question":
        options = data.get("options") or []
        option_lines = [f"- {option}" for option in options]
        return "\n".join(
            [
                "Tri-System DES Question",
                data.get("text", ""),
                "Options:",
                *option_lines,
            ]
        )

    if state_type == "result":
        return "\n".join(
            [
                "Tri-System DES Result",
                repr(data),
            ]
        )

    if state_type == "axis_preview":
        fields = [
            ("trigger", data.get("trigger", "")),
            ("classification", data.get("classification", "")),
            ("next_action", data.get("next_action", "")),
            ("reference", data.get("reference")),
            ("stability", data.get("stability")),
            ("impact", data.get("impact")),
        ]
        return "\n".join(
            [
                "Tri-System AXIS Preview",
                f"CLASSIFICATION: {data.get('classification', '')}",
                f"NEXT ACTION: {data.get('next_action', '')}",
                *[f"{key}: {value}" for key, value in fields],
            ]
        )

    if state_type == "confirm":
        payload = data.get("payload") or {}
        return "\n".join(
            [
                "Tri-System Confirmation",
                data.get("prompt", ""),
                "Payload:",
                f"trigger: {payload.get('trigger', '')}",
                f"classification: {payload.get('classification', '')}",
                f"next_action: {payload.get('next_action', '')}",
                f"reference: {payload.get('reference')}",
                f"stability: {payload.get('stability')}",
                f"impact: {payload.get('impact')}",
                "Options: Confirm / Cancel",
            ]
        )

    if state_type == "axis_result":
        return "\n".join(
            [
                "Tri-System AXIS Result",
                repr(data),
            ]
        )

    if state_type == "error":
        return "\n".join(
            [
                "Tri-System Error",
                data.get("message", "Unknown error."),
                f"Recoverable: {data.get('recoverable')}",
            ]
        )

    return "Tri-System Flow\nUnknown state."
