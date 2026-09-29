"""Session layer: SessionService / SessionStore persistence of history entries.

S5: ExecutionService was retired, so nothing in the runtime appends entries
any more. These tests seed entries through SessionService.append_to_session
with the result shapes the retired service produced, so the stored format
that existing history depends on stays pinned.
"""

import unittest
import uuid
from copy import deepcopy
from pathlib import Path

from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore

AXIS_SESSION_ID = "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1"

# Shape of a verified success result produced before S5.
SUCCESS_RESULT = {
    "ok": True,
    "axis": {
        "session_id": AXIS_SESSION_ID,
        "outcome": "reduced",
        "clarity_rating": 7,
        "steps_completed": 3,
        "continuity_before": 40,
        "continuity_after": 55,
        "protocol_output": "done",
    },
    "pipeline": {"source": "axis_adapter", "status_code": 200},
}

# Shape of a boundary failure result produced before S5.
BOUNDARY_FAILURE_RESULT = {
    "ok": False,
    "error_type": "boundary_violation",
    "message": "Request rejected by AXIS boundary rules.",
    "safe_details": {"violation_type": "forbidden_endpoint", "endpoint": None},
}


class SessionLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.store = SessionStore(root_dir=self.tmp_root / "sessions", store_full_trigger=True)
        self.session_service = SessionService(session_store=self.store)

    def _cleanup_tmp_root(self):
        if not self.tmp_root.exists():
            return
        for path in sorted(self.tmp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.tmp_root.rmdir()

    def _append(self, session_id, result, trigger="t"):
        return self.session_service.append_to_session(
            session_id=session_id,
            execution_result=deepcopy(result),
            trigger=trigger,
            operator_id="op_1",
        )

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
        self._append(session["session_id"], SUCCESS_RESULT, "Do thing")
        loaded = self.session_service.get_session(session["session_id"])
        self.assertEqual(len(loaded["entries"]), 1)
        entry = loaded["entries"][0]
        self.assertEqual(entry["result_type"], "success")
        self.assertEqual(entry["axis"]["session_id"], AXIS_SESSION_ID)
        self.assertEqual(entry["axis"]["outcome"], "reduced")

    def test_session_retrieval_returns_full_history(self):
        session = self.session_service.create_session("op_1")
        self._append(session["session_id"], SUCCESS_RESULT, "One")
        self._append(session["session_id"], SUCCESS_RESULT, "Two")
        loaded = self.session_service.get_session(session["session_id"])
        self.assertEqual(len(loaded["entries"]), 2)

    def test_session_does_not_mutate_execution_result(self):
        session = self.session_service.create_session("op_1")
        result = deepcopy(SUCCESS_RESULT)
        before = deepcopy(result)
        self.session_service.append_to_session(
            session_id=session["session_id"], execution_result=result, trigger="t", operator_id="op_1"
        )
        loaded = self.session_service.get_session(session["session_id"])
        self.assertEqual(result, before)
        self.assertEqual(loaded["entries"][0]["axis"]["continuity_after"], 55)

    def test_failure_responses_stored_correctly(self):
        session = self.session_service.create_session("op_1")
        self._append(session["session_id"], BOUNDARY_FAILURE_RESULT, "Forbidden")
        loaded = self.session_service.get_session(session["session_id"])
        entry = loaded["entries"][0]
        self.assertEqual(entry["result_type"], "failure")
        self.assertEqual(entry["failure"]["error_type"], "boundary_violation")
        self.assertEqual(entry["axis"], {})

    def test_append_rejects_operator_mismatch(self):
        session = self.session_service.create_session("op_1")
        with self.assertRaises(ValueError):
            self.session_service.append_to_session(
                session_id=session["session_id"],
                execution_result=deepcopy(SUCCESS_RESULT),
                trigger="t",
                operator_id="op_2",
            )
        self.assertEqual(self.session_service.get_session(session["session_id"])["entries"], [])

    def test_pipeline_metadata_is_not_stored(self):
        session = self.session_service.create_session("op_1")
        self._append(session["session_id"], SUCCESS_RESULT, "No pipeline persistence")
        loaded = self.session_service.get_session(session["session_id"])
        entry = loaded["entries"][0]
        self.assertIn("axis", entry)
        self.assertNotIn("pipeline", entry)

    def test_trigger_stored_according_to_policy(self):
        session = self.session_service.create_session("op_1")
        self._append(session["session_id"], SUCCESS_RESULT, "Store this trigger")
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
