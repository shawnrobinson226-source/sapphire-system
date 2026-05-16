"""Minimal web bridge for the Sapphire -> DES -> AXIS tri-system flow."""

from __future__ import annotations

from typing import Callable

from core.des.tri_system_flow import TriSystemFlow
from ui.views import render_tri_state


TRI_START_TRIGGERS = {"tri", "/tri"}
TRI_CONFIRM_COMMAND = "confirm"
TRI_REJECT_COMMANDS = {"reject", "cancel"}


class WebTriSystemBridge:
    """Drive TriSystemFlow from chat text without involving the LLM/tool path."""

    def __init__(self, flow_factory: Callable[[], TriSystemFlow] = TriSystemFlow):
        self.flow_factory = flow_factory
        self.flow: TriSystemFlow | None = None
        self.active = False

    def handle(self, text: str) -> str | None:
        command = self._normalize(text)
        if not self.active:
            if command not in TRI_START_TRIGGERS:
                return None
            self.flow = self.flow_factory()
            self.active = True
            return self._render_terminal_if_needed(self.flow.start())

        if self.flow is None:
            self.active = False
            return None

        if self._awaiting_confirmation():
            if command == TRI_CONFIRM_COMMAND:
                state = self.flow.confirm()
                self.active = False
                return render_tri_state(state)
            if command in TRI_REJECT_COMMANDS:
                state = self.flow.cancel()
                self.active = False
                return render_tri_state(state)
            return (
                "Tri-System confirmation pending.\n"
                "Type confirm to execute AXIS, or reject to cancel."
            )

        state = self.flow.submit_answer(text)
        if state.get("type") == "result":
            return self._render_result_preview_confirm(state)
        return self._render_terminal_if_needed(state)

    def _render_result_preview_confirm(self, state: dict) -> str:
        if self.flow is None:
            return render_tri_state(state)
        preview = self.flow.axis_preview()
        confirm = self.flow.confirm_state()
        return "\n\n".join(
            part
            for part in [
                render_tri_state(state),
                render_tri_state(preview),
                render_tri_state(confirm),
            ]
            if part
        )

    def _render_terminal_if_needed(self, state: dict) -> str:
        if state.get("type") in {"error", "idle", "axis_result"}:
            self.active = False
        return render_tri_state(state)

    def _awaiting_confirmation(self) -> bool:
        if self.flow is None:
            return False
        return self.flow.question is None and self.flow.pending_execution is not None

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").strip().lower()


_WEB_TRI_SYSTEM_BRIDGE = WebTriSystemBridge()


def get_web_tri_system_bridge() -> WebTriSystemBridge:
    return _WEB_TRI_SYSTEM_BRIDGE
