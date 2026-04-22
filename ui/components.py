"""Minimal UI panel components for Sapphire execution surface."""

from __future__ import annotations

from ui.state import UIState
from ui.views import render_history_entry, render_result


def SessionControls(state: UIState) -> str:
    return "\n".join(
        [
            "Session",
            f"Operator ID: {state.operator_id or 'N/A'}",
            f"Current Session: {state.session_id or 'N/A'}",
        ]
    )


def TriggerForm(_: UIState) -> str:
    return "\n".join(
        [
            "Submit Trigger",
            "Enter trigger text and submit once.",
        ]
    )


def ResultView(state: UIState) -> str:
    body = render_result(state.latest_response)
    return "Latest Result" if not body else f"Latest Result\n{body}"


def HistoryView(state: UIState) -> str:
    if not state.session_history:
        return "Session History"
    blocks = [render_history_entry(entry) for entry in state.session_history]
    return "Session History\n" + "\n".join(blocks)


def AppShell(state: UIState) -> str:
    return "\n\n".join(
        [
            SessionControls(state),
            TriggerForm(state),
            ResultView(state),
            HistoryView(state),
        ]
    )
