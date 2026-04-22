"""Session service for appending and retrieving execution timeline entries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.sapphire.session_store import SessionStore


class SessionService:
    """Storage-only session timeline service with no interpretation logic."""

    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _clean_non_empty(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required.")
        return value.strip()

    def create_session(self, operator_id: str) -> dict:
        return self.session_store.create_session(operator_id)

    def get_session(self, session_id: str) -> dict | None:
        return self.session_store.get_session(session_id)

    def append_to_session(
        self,
        session_id: str,
        execution_result: dict[str, Any],
        trigger: str,
        operator_id: str,
    ) -> dict:
        clean_session_id = self._clean_non_empty(session_id, "session_id")
        clean_operator_id = self._clean_non_empty(operator_id, "operator_id")
        session = self.session_store.get_session(clean_session_id)
        if not session:
            raise ValueError(f"Session not found: {clean_session_id}")
        if session.get("operator_id") != clean_operator_id:
            raise ValueError("Session/operator mismatch.")

        axis_data = execution_result.get("axis")
        if not isinstance(axis_data, dict):
            axis_data = {}

        entry = {
            "timestamp": self._now_iso(),
            **self.session_store._trigger_field(trigger),
            # Store AXIS payload only. Never persist pipeline metadata.
            "axis": dict(axis_data),
        }

        if execution_result.get("gated"):
            entry["gated"] = {
                "gate_type": execution_result.get("gate_type"),
                "message": execution_result.get("message", ""),
            }
            entry["result_type"] = "gated"
        elif execution_result.get("ok"):
            entry["result_type"] = "success"
        else:
            entry["failure"] = {
                "error_type": execution_result.get("error_type"),
                "message": execution_result.get("message"),
            }
            entry["result_type"] = "failure"

        return self.session_store.append_entry(clean_session_id, entry)
