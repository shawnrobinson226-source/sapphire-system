"""Local-first Sapphire UI shell built on session/renderer layers and the tri flow.

S5: direct AXIS execution (submit_trigger) was removed. AXIS is reached only
through the governed tri flow: DES decision, preview, operator confirm.
"""

from __future__ import annotations

from typing import Any, Callable

from core.des.tri_system_flow import TriSystemFlow
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore
from ui.components import AppShell
from ui.state import UIState


class SapphireUIApp:
    """Minimal UI controller for session + trigger + result + history panels."""

    def __init__(
        self,
        *,
        session_service: SessionService | None = None,
        state: UIState | None = None,
        tri_flow: TriSystemFlow | None = None,
        tri_flow_factory: Callable[[], TriSystemFlow] | None = None,
    ):
        self.state = state or UIState()
        if session_service is None:
            session_store = SessionStore()
            session_service = SessionService(session_store=session_store)
        self.session_service = session_service
        self.tri_flow_factory = tri_flow_factory or TriSystemFlow
        self.tri_flow = tri_flow or self.tri_flow_factory()

    @staticmethod
    def _clean_non_empty(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required.")
        return value.strip()

    def create_new_session(self, operator_id: str) -> str:
        clean_operator_id = self._clean_non_empty(operator_id, "operator_id")
        session = self.session_service.create_session(clean_operator_id)
        self.state.operator_id = clean_operator_id
        self.state.session_id = session["session_id"]
        self.state.session_history = []
        self.state.safe_error = ""
        return session["session_id"]

    def select_session(self, operator_id: str, session_id: str) -> bool:
        clean_operator_id = self._clean_non_empty(operator_id, "operator_id")
        clean_session_id = self._clean_non_empty(session_id, "session_id")
        session = self.session_service.get_session(clean_session_id)
        if not session:
            self.state.safe_error = "session not found."
            return False
        if session.get("operator_id") != clean_operator_id:
            self.state.safe_error = "session/operator mismatch."
            return False
        self.state.operator_id = clean_operator_id
        self.state.session_id = clean_session_id
        self.state.session_history = list(session.get("entries", []))
        self.state.safe_error = ""
        return True

    def show_session(self, session_id: str) -> list[dict[str, Any]]:
        clean_session_id = self._clean_non_empty(session_id, "session_id")
        session = self.session_service.get_session(clean_session_id)
        if not session:
            self.state.safe_error = "session not found."
            return []
        self.state.session_history = list(session.get("entries", []))
        self.state.safe_error = ""
        return self.state.session_history

    def start_tri_flow(self) -> dict[str, Any]:
        self.tri_flow = self.tri_flow_factory()
        self.state.tri_des_result = None
        self.state.tri_axis_preview = None
        self.state.tri_state = self.tri_flow.start()
        return self.state.tri_state

    def submit_tri_answer(self, answer: str) -> dict[str, Any]:
        state = self.tri_flow.submit_answer(answer)
        if state.get("type") == "result":
            self.state.tri_des_result = state
            self.state.tri_axis_preview = self.tri_flow.axis_preview()
            self.state.tri_state = self.tri_flow.confirm_state()
        else:
            self.state.tri_state = state
        return self.state.tri_state

    def confirm_tri_flow(self) -> dict[str, Any]:
        self.state.tri_state = self.tri_flow.confirm()
        return self.state.tri_state

    def cancel_tri_flow(self) -> dict[str, Any]:
        self.state.tri_des_result = None
        self.state.tri_axis_preview = None
        self.state.tri_state = self.tri_flow.cancel()
        return self.state.tri_state

    def get_tri_trace(self) -> list[dict[str, Any]]:
        return self.tri_flow.get_trace()

    def render(self) -> str:
        return AppShell(self.state)


def main() -> int:
    app = SapphireUIApp()
    print("Sapphire UI Surface")
    while True:
        command = input("Command (new/use/show/render/tri/tri-trace/exit): ").strip().lower()
        if command == "exit":
            return 0
        if command == "new":
            operator_id = input("Operator ID: ").strip()
            try:
                session_id = app.create_new_session(operator_id)
                print(session_id)
            except ValueError as exc:
                print(str(exc))
            continue
        if command == "use":
            operator_id = input("Operator ID: ").strip()
            session_id = input("Session ID: ").strip()
            ok = app.select_session(operator_id, session_id)
            print("ok" if ok else app.state.safe_error)
            continue
        if command == "show":
            session_id = input("Session ID: ").strip()
            app.show_session(session_id)
            print(app.render())
            continue
        if command == "render":
            print(app.render())
            continue
        if command == "tri":
            state = app.start_tri_flow()
            while state.get("type") == "question":
                print(app.render())
                answer = input("Answer: ")
                state = app.submit_tri_answer(answer)
            print(app.render())
            if state.get("type") == "confirm":
                choice = input("Confirm Execution or Reject: ").strip().lower()
                if choice in {"confirm", "confirm execution"}:
                    app.confirm_tri_flow()
                else:
                    app.cancel_tri_flow()
                print(app.render())
            continue
        if command == "tri-trace":
            print({"trace": app.get_tri_trace()})
            continue
        print("Unknown command.")


if __name__ == "__main__":
    raise SystemExit(main())
