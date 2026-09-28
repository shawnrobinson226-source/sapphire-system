"""SapphireUIApp surface: session selection and history rendering.

S5: direct AXIS execution (submit_trigger) was removed from the UI. History is
seeded through SessionService / SessionStore with the entry shapes existing
sessions hold, and must keep rendering.
"""

import unittest
import uuid
from pathlib import Path

from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore
from ui.app import SapphireUIApp
from ui.state import UIState

AXIS_SESSION_ID = "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1"


class _NoTriFlow:
    """Stand-in tri flow: these tests never start the tri flow."""


class UISurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.session_store = SessionStore(root_dir=self.tmp_root / "sessions")
        self.session_service = SessionService(session_store=self.session_store)
        self.app = SapphireUIApp(
            session_service=self.session_service,
            state=UIState(),
            tri_flow=_NoTriFlow(),
        )

    def _cleanup_tmp_root(self):
        if not self.tmp_root.exists():
            return
        for path in sorted(self.tmp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.tmp_root.rmdir()

    def _assert_no_interpretation_text(self, text: str):
        banned = ["you should", "i recommend", "this means", "consider", "suggests that", "it appears"]
        lower = text.lower()
        for phrase in banned:
            self.assertNotIn(phrase, lower)

    def _append_success(self, session_id: str, trigger: str = "t"):
        self.session_service.append_to_session(
            session_id=session_id,
            execution_result={
                "ok": True,
                "axis": {"session_id": AXIS_SESSION_ID, "outcome": "reduced", "protocol_output": "done"},
                "pipeline": {"source": "axis_adapter", "status_code": 200},
            },
            trigger=trigger,
            operator_id="op_100",
        )

    def _append_failure(self, session_id: str):
        self.session_service.append_to_session(
            session_id=session_id,
            execution_result={
                "ok": False,
                "error_type": "boundary_violation",
                "message": "Request rejected by AXIS boundary rules.",
            },
            trigger="Bad route",
            operator_id="op_100",
        )

    def _append_legacy_entry(self, session_id: str, entry: dict):
        """Write a pre-S2 stored entry directly, as legacy sessions hold them."""
        self.session_store.append_entry(session_id, {"timestamp": "legacy", "trigger": "t", **entry})

    def test_direct_axis_execution_is_removed(self):
        self.assertFalse(hasattr(SapphireUIApp, "submit_trigger"))
        self.assertFalse(hasattr(self.app, "execution_service"))

    def test_creating_and_selecting_session(self):
        sid = self.app.create_new_session("op_100")
        self.assertTrue(sid)
        self.assertEqual(self.app.state.session_id, sid)
        selected = self.app.select_session("op_100", sid)
        self.assertTrue(selected)
        self.assertEqual(self.app.state.operator_id, "op_100")

    def test_select_session_rejects_operator_mismatch(self):
        sid = self.app.create_new_session("op_100")
        self.assertFalse(self.app.select_session("op_other", sid))
        self.assertEqual(self.app.state.safe_error, "session/operator mismatch.")

    def test_select_session_loads_existing_history(self):
        sid = self.app.create_new_session("op_100")
        self._append_success(sid)
        self.app.state.session_history = []
        self.assertTrue(self.app.select_session("op_100", sid))
        self.assertEqual(len(self.app.state.session_history), 1)

    def test_success_history_rendering(self):
        sid = self.app.create_new_session("op_100")
        self._append_success(sid)
        self.app.show_session(sid)
        output = self.app.render()
        self.assertIn("=== AXIS RESULT ===", output)
        self.assertIn(f"Session: {AXIS_SESSION_ID}", output)
        self.assertIn("Outcome: reduced", output)
        self.assertIn("Protocol Output: done", output)

    def test_failure_history_rendering(self):
        sid = self.app.create_new_session("op_100")
        self._append_failure(sid)
        self.app.show_session(sid)
        output = self.app.render()
        self.assertIn("=== EXECUTION FAILURE ===", output)
        self.assertIn("Type: boundary_violation", output)

    def test_session_history_rendering(self):
        sid = self.app.create_new_session("op_100")
        self._append_success(sid, "First")
        # A legacy gated entry may hold AXIS free text; it renders with a
        # fixed pause message instead.
        self._append_legacy_entry(
            sid,
            {"axis": {}, "gated": {"gate_type": "breath", "message": "Pause."}, "result_type": "gated"},
        )
        history = self.app.show_session(sid)
        self.assertEqual(len(history), 2)
        output = self.app.render()
        self.assertIn("Session History", output)
        self.assertIn("--- Entry [", output)
        self.assertIn("=== AXIS RESULT ===", output)
        self.assertIn("=== SYSTEM PAUSE === Legacy pause entry. Stored message is not displayed.", output)
        self.assertNotIn("Pause.", output)

    def test_show_unknown_session_is_safe(self):
        self.assertEqual(self.app.show_session("missing"), [])
        self.assertEqual(self.app.state.safe_error, "session not found.")

    def test_ui_does_not_expose_pipeline_metadata(self):
        sid = self.app.create_new_session("op_100")
        self._append_success(sid)
        self.app.show_session(sid)
        output = self.app.render()
        self.assertNotIn("pipeline", output.lower())
        self.assertNotIn("axis_adapter", output)
        self.assertNotIn("status_code", output)

    def test_ui_does_not_add_interpretation_text(self):
        sid = self.app.create_new_session("op_100")
        self._append_success(sid)
        self.app.show_session(sid)
        self._assert_no_interpretation_text(self.app.render())

    def test_legacy_success_entry_protocol_step_order_preserved(self):
        # Legacy stored success entries keep their layout and still render.
        sid = self.app.create_new_session("op_100")
        self._append_legacy_entry(
            sid,
            {
                "axis": {
                    "classification": "stable",
                    "protocol": ["first step", "second step", "third step"],
                    "action": "first step",
                    "outcome": "done",
                    "continuity": "cont-1",
                },
                "result_type": "success",
            },
        )
        self.app.show_session(sid)
        output = self.app.render()
        self.assertIn("Classification: stable", output)
        p1 = output.index("1. first step")
        p2 = output.index("2. second step")
        p3 = output.index("3. third step")
        self.assertTrue(p1 < p2 < p3)


if __name__ == "__main__":
    unittest.main()
