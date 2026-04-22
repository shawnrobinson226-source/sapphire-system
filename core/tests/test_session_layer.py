import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest import mock

from core.sapphire.execution_service import ExecutionService
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore


class SessionLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.store = SessionStore(root_dir=self.tmp_root / "sessions", store_full_trigger=True)
        self.session_service = SessionService(session_store=self.store)
        self.adapter = mock.Mock()
        self.execution_service = ExecutionService(
            axis_adapter=self.adapter,
            session_service=self.session_service,
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

    def _mock_success(self):
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {
                "classification": "stable",
                "protocol": {"steps": ["a", "b"]},
                "action": "a",
                "outcome": "ok",
                "continuity": "c-1",
            },
        }

    def test_session_creation_works(self):
        session = self.session_service.create_session("op_1")
        self.assertTrue(session["session_id"])
        self.assertEqual(session["operator_id"], "op_1")
        self.assertEqual(session["entries"], [])
        loaded = self.session_service.get_session(session["session_id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["session_id"], session["session_id"])

    def test_entries_append_correctly(self):
        session = self.session_service.create_session("op_1")
        self._mock_success()
        self.execution_service.execute("Do thing", operator_id="op_1", session_id=session["session_id"])
        loaded = self.session_service.get_session(session["session_id"])
        self.assertEqual(len(loaded["entries"]), 1)
        entry = loaded["entries"][0]
        self.assertEqual(entry["result_type"], "success")
        self.assertEqual(entry["axis"]["classification"], "stable")

    def test_session_retrieval_returns_full_history(self):
        session = self.session_service.create_session("op_1")
        self._mock_success()
        self.execution_service.execute("One", operator_id="op_1", session_id=session["session_id"])
        self.execution_service.execute("Two", operator_id="op_1", session_id=session["session_id"])
        loaded = self.session_service.get_session(session["session_id"])
        self.assertEqual(len(loaded["entries"]), 2)

    def test_execution_without_session_still_works(self):
        self._mock_success()
        result = self.execution_service.execute("Stateless run", operator_id="op_1")
        self.assertTrue(result["ok"])
        session_files = list((self.tmp_root / "sessions").glob("*.json"))
        self.assertEqual(session_files, [])

    def test_session_does_not_mutate_execution_result(self):
        session = self.session_service.create_session("op_1")
        self._mock_success()
        result = self.execution_service.execute("Mutability check", operator_id="op_1", session_id=session["session_id"])
        before = deepcopy(result)
        loaded = self.session_service.get_session(session["session_id"])
        self.assertEqual(result, before)
        self.assertEqual(loaded["entries"][0]["axis"]["continuity"], "c-1")

    def test_gated_responses_stored_correctly(self):
        session = self.session_service.create_session("op_1")
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {"gated": True, "gate_type": "breath", "message": "Pause."},
        }
        self.execution_service.execute("Need pause", operator_id="op_1", session_id=session["session_id"])
        loaded = self.session_service.get_session(session["session_id"])
        entry = loaded["entries"][0]
        self.assertEqual(entry["result_type"], "gated")
        self.assertEqual(entry["gated"]["gate_type"], "breath")
        self.assertEqual(entry["gated"]["message"], "Pause.")

    def test_failure_responses_stored_correctly(self):
        session = self.session_service.create_session("op_1")
        self.adapter.call_axis.return_value = {
            "ok": False,
            "status_code": 0,
            "error": "boundary_violation",
            "violation_type": "forbidden_endpoint",
            "endpoint": "POST /api/v2/execute",
        }
        self.execution_service.execute("Forbidden", operator_id="op_1", session_id=session["session_id"])
        loaded = self.session_service.get_session(session["session_id"])
        entry = loaded["entries"][0]
        self.assertEqual(entry["result_type"], "failure")
        self.assertEqual(entry["failure"]["error_type"], "boundary_violation")

    def test_pipeline_metadata_is_not_stored(self):
        session = self.session_service.create_session("op_1")
        self._mock_success()
        self.execution_service.execute("No pipeline persistence", operator_id="op_1", session_id=session["session_id"])
        loaded = self.session_service.get_session(session["session_id"])
        entry = loaded["entries"][0]
        self.assertIn("axis", entry)
        self.assertNotIn("pipeline", entry)

    def test_trigger_stored_according_to_policy(self):
        session = self.session_service.create_session("op_1")
        self._mock_success()
        self.execution_service.execute("Store this trigger", operator_id="op_1", session_id=session["session_id"])
        loaded = self.session_service.get_session(session["session_id"])
        self.assertEqual(loaded["entries"][0]["trigger"], "Store this trigger")
        self.assertNotIn("trigger_hash", loaded["entries"][0])

        hashed_store = SessionStore(root_dir=self.tmp_root / "sessions_hashed", store_full_trigger=False)
        hashed_service = SessionService(session_store=hashed_store)
        hashed_session = hashed_service.create_session("op_1")
        hashed_service.append_to_session(
            session_id=hashed_session["session_id"],
            execution_result={"ok": False, "error_type": "validation_error", "message": "x"},
            trigger="Sensitive text",
            operator_id="op_1",
        )
        loaded_hashed = hashed_service.get_session(hashed_session["session_id"])
        entry = loaded_hashed["entries"][0]
        self.assertIn("trigger_hash", entry)
        self.assertNotIn("trigger", entry)
        self.assertEqual(len(entry["trigger_hash"]), 16)


if __name__ == "__main__":
    unittest.main()
