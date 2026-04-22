import unittest
import uuid
from pathlib import Path
from unittest import mock

from core.sapphire.execution_service import ExecutionService
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore
from ui.app import SapphireUIApp
from ui.state import UIState


class UISurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.session_store = SessionStore(root_dir=self.tmp_root / "sessions")
        self.session_service = SessionService(session_store=self.session_store)
        self.adapter = mock.Mock()
        self.execution_service = ExecutionService(
            axis_adapter=self.adapter,
            session_service=self.session_service,
        )
        self.app = SapphireUIApp(
            execution_service=self.execution_service,
            session_service=self.session_service,
            state=UIState(),
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

    def _mock_success(self):
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {
                "classification": "stable",
                "protocol": ["first step", "second step", "third step"],
                "action": "first step",
                "outcome": "done",
                "continuity": "cont-1",
            },
        }

    def test_creating_and_selecting_session(self):
        sid = self.app.create_new_session("op_100")
        self.assertTrue(sid)
        self.assertEqual(self.app.state.session_id, sid)
        selected = self.app.select_session("op_100", sid)
        self.assertTrue(selected)
        self.assertEqual(self.app.state.operator_id, "op_100")

    def test_successful_trigger_submission(self):
        self.app.create_new_session("op_100")
        self._mock_success()
        result = self.app.submit_trigger("Run now")
        self.assertTrue(result["ok"])
        self.assertIn("axis", result)
        self.assertEqual(len(self.app.state.session_history), 1)

    def test_success_result_rendering(self):
        self.app.create_new_session("op_100")
        self._mock_success()
        self.app.submit_trigger("Render success")
        output = self.app.render()
        self.assertIn("Latest Result", output)
        self.assertIn("=== AXIS RESULT ===", output)
        self.assertIn("Classification: stable", output)

    def test_gated_result_rendering(self):
        self.app.create_new_session("op_100")
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {"gated": True, "gate_type": "breath", "message": "Pause."},
        }
        self.app.submit_trigger("Need gate")
        output = self.app.render()
        self.assertIn("=== SYSTEM PAUSE === Pause.", output)
        self.assertNotIn("=== EXECUTION FAILURE ===", output)

    def test_failure_rendering(self):
        self.app.create_new_session("op_100")
        self.adapter.call_axis.return_value = {
            "ok": False,
            "status_code": 0,
            "error": "boundary_violation",
            "violation_type": "forbidden_endpoint",
            "endpoint": "POST /api/v2/execute",
        }
        self.app.submit_trigger("Bad route")
        output = self.app.render()
        self.assertIn("=== EXECUTION FAILURE ===", output)
        self.assertIn("Type: boundary_violation", output)

    def test_session_history_rendering(self):
        sid = self.app.create_new_session("op_100")
        self._mock_success()
        self.app.submit_trigger("First")
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {"gated": True, "gate_type": "breath", "message": "Pause."},
        }
        self.app.submit_trigger("Second")
        history = self.app.show_session(sid)
        self.assertEqual(len(history), 2)
        output = self.app.render()
        self.assertIn("Session History", output)
        self.assertIn("--- Entry [", output)
        self.assertIn("=== AXIS RESULT ===", output)
        self.assertIn("=== SYSTEM PAUSE === Pause.", output)

    def test_ui_does_not_expose_pipeline_metadata(self):
        self.app.create_new_session("op_100")
        self._mock_success()
        self.app.submit_trigger("No pipeline leak")
        output = self.app.render()
        self.assertNotIn("pipeline", output.lower())
        self.assertNotIn("axis_adapter", output)
        self.assertNotIn("status_code", output)

    def test_ui_does_not_add_interpretation_text(self):
        self.app.create_new_session("op_100")
        self._mock_success()
        self.app.submit_trigger("No interpretation")
        output = self.app.render()
        self._assert_no_interpretation_text(output)

    def test_protocol_step_order_preserved(self):
        self.app.create_new_session("op_100")
        self._mock_success()
        self.app.submit_trigger("Protocol ordering")
        output = self.app.render()
        p1 = output.index("1. first step")
        p2 = output.index("2. second step")
        p3 = output.index("3. third step")
        self.assertTrue(p1 < p2 < p3)


if __name__ == "__main__":
    unittest.main()
