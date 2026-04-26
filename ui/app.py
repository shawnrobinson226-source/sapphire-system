"""Local-first Sapphire UI shell built on execution/session/renderer layers."""

from __future__ import annotations

import os
from typing import Any, Callable

from core.des.tri_system_flow import TriSystemFlow
from core.sapphire.axis_adapter import AxisAdapter
from core.sapphire.execution_service import ExecutionService
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore
from ui.components import AppShell
from ui.state import UIState


class SapphireUIApp:
    """Minimal UI controller for session + trigger + result + history panels."""

    def __init__(
        self,
        *,
        execution_service: ExecutionService | None = None,
        session_service: SessionService | None = None,
        state: UIState | None = None,
        axis_base_url: str | None = None,
        tri_flow: TriSystemFlow | None = None,
        tri_flow_factory: Callable[[], TriSystemFlow] | None = None,
    ):
        self.state = state or UIState()
        if session_service is None:
            session_store = SessionStore()
            session_service = SessionService(session_store=session_store)
        self.session_service = session_service

        if execution_service is None:
            adapter = AxisAdapter(axis_base_url=axis_base_url or os.environ.get("AXIS_BASE_URL", "http://localhost:3000"))
            execution_service = ExecutionService(axis_adapter=adapter, session_service=self.session_service)
        self.execution_service = execution_service
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

    def submit_trigger(self, trigger: str) -> dict:
        clean_operator_id = self._clean_non_empty(self.state.operator_id, "operator_id")
        clean_trigger = self._clean_non_empty(trigger, "trigger")
        self.state.loading = True
        try:
            result = self.execution_service.execute(
                clean_trigger,
                operator_id=clean_operator_id,
                session_id=self.state.session_id or None,
            )
            self.state.latest_response = result
            if self.state.session_id:
                session = self.session_service.get_session(self.state.session_id)
                self.state.session_history = list((session or {}).get("entries", []))
            self.state.safe_error = ""
            return result
        finally:
            self.state.loading = False

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

    def render(self) -> str:
        return AppShell(self.state)


def main() -> int:
    app = SapphireUIApp()
    print("Sapphire UI Surface")
    while True:
        command = input("Command (new/use/submit/show/render/tri/exit): ").strip().lower()
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
        if command == "submit":
            trigger = input("Trigger: ").strip()
            try:
                app.submit_trigger(trigger)
                print(app.render())
            except ValueError as exc:
                print(str(exc))
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
                choice = input("Confirm or Cancel: ").strip().lower()
                if choice == "confirm":
                    app.confirm_tri_flow()
                else:
                    app.cancel_tri_flow()
                print(app.render())
            continue
        print("Unknown command.")


if __name__ == "__main__":
    raise SystemExit(main())
