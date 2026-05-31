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
        return "Review Action\nIdle"

    if state_type == "question":
        options = data.get("options") or []
        option_lines = [f"- {option}" for option in options]
        return "\n".join(
            [
                "A few questions",
                data.get("text", ""),
                "Options:",
                *option_lines,
            ]
        )

    if state_type == "result":
        return "\n".join(
            [
                "Decision Summary",
                repr(data),
            ]
        )

    if state_type == "axis_preview":
        fields = [
            ("trigger", data.get("trigger", "")),
            ("Category", data.get("classification", "")),
            ("Next Step", data.get("next_action", "")),
            ("reference", data.get("reference")),
            ("stability", data.get("stability")),
            ("impact", data.get("impact")),
        ]
        return "\n".join(
            [
                "Proposed Action",
                f"CATEGORY: {data.get('classification', '')}",
                f"NEXT STEP: {data.get('next_action', '')}",
                *[f"{key}: {value}" for key, value in fields],
            ]
        )

    if state_type == "confirm":
        payload = data.get("payload") or {}
        return "\n".join(
            [
                "Proposed Action",
                f"Category: {payload.get('classification', '')}",
                f"Next Step: {payload.get('next_action', '')}",
                f"Trigger: {payload.get('trigger', '')}",
                "[Confirm Execution]",
                "[Reject]",
            ]
        )

    if state_type == "axis_result":
        outcome = data.get("outcome") or "completed"
        protocol_output = data.get("protocol_output") or ""
        session_id = data.get("sessionId") or data.get("session_id") or ""

        lines = [
            "Action Result",
            f"Status: {str(outcome).replace('_', ' ').title()}",
        ]

        if protocol_output:
            lines.extend(["", protocol_output])

        if session_id:
            lines.extend(["", f"Reference: {session_id}"])

        return "\n".join(lines)

    if state_type == "error":
        return "\n".join(
            [
                "Review Action Error",
                data.get("message", "Unknown error."),
                f"Recoverable: {data.get('recoverable')}",
            ]
        )

    return "Review Action\nUnknown state."
