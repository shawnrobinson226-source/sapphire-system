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
