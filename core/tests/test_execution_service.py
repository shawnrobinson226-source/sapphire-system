import json
import unittest
import uuid
from pathlib import Path
from unittest import mock

from core.sapphire.execution_service import ExecutionService
from core.security import violations


class ExecutionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.log_path = self.tmp_root / "logs" / "sapphire_boundary_violations.log"
        self.violations_patch = mock.patch.object(violations, "VIOLATION_LOG_PATH", self.log_path)
        self.violations_patch.start()
        self.addCleanup(self.violations_patch.stop)
        self.adapter = mock.Mock()
        self.service = ExecutionService(axis_adapter=self.adapter)

    def _cleanup_tmp_root(self):
        if not self.tmp_root.exists():
            return
        for path in sorted(self.tmp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.tmp_root.rmdir()

    def _read_log_lines(self):
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_valid_input_returns_success_shape(self):
        # S2: success requires a verified AXIS execute result (data.sessionId);
        # the result carries only named contract fields.
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {
                "ok": True,
                "sessionId": "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1",
                "outcome": "reduced",
                "clarity_rating": 7,
                "steps_completed": 3,
                "continuity_before": 40,
                "continuity_after": 55,
                "protocol_output": "done",
            },
        }
        result = self.service.execute("Ship patch", operator_id="op_123")
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["axis"],
            {
                "session_id": "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1",
                "outcome": "reduced",
                "clarity_rating": 7,
                "steps_completed": 3,
                "continuity_before": 40,
                "continuity_after": 55,
                "protocol_output": "done",
            },
        )
        self.assertEqual(result["pipeline"]["source"], "axis_adapter")
        self.assertEqual(result["pipeline"]["status_code"], 200)
        self.adapter.call_axis.assert_called_once_with(
            "POST",
            "/api/v2/execute",
            "op_123",
            payload={"trigger": "Ship patch"},
        )

    def test_missing_operator_id_returns_validation_failure(self):
        result = self.service.execute("Do work", operator_id="")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "validation_error")
        self.assertEqual(result["safe_details"]["field"], "operator_id")
        self.adapter.call_axis.assert_not_called()
        logs = self._read_log_lines()
        self.assertEqual(logs[-1]["violation_type"], "validation_error")
        self.assertEqual(logs[-1]["details"]["value_shapes"]["field"]["type"], "str")

    def test_empty_trigger_returns_validation_failure(self):
        result = self.service.execute("   ", operator_id="op_123")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "validation_error")
        self.assertEqual(result["safe_details"]["field"], "trigger")
        self.adapter.call_axis.assert_not_called()
        logs = self._read_log_lines()
        self.assertEqual(logs[-1]["violation_type"], "validation_error")

    def test_boundary_violation_from_adapter_is_handled(self):
        self.adapter.call_axis.return_value = {
            "ok": False,
            "status_code": 0,
            "error": "boundary_violation",
            "violation_type": "forbidden_endpoint",
            "endpoint": "POST /api/v2/execute",
        }
        result = self.service.execute("Do work", operator_id="op_123")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "boundary_violation")
        self.assertIn("rejected", result["message"].lower())
        self.assertEqual(result["safe_details"]["violation_type"], "forbidden_endpoint")
        logs = self._read_log_lines()
        self.assertEqual(logs[-1]["violation_type"], "boundary_violation")

    def test_adapter_success_data_passes_through_without_reclassification(self):
        # S2: only named contract fields are copied, unchanged; fields outside
        # the contract (e.g. a classification from AXIS) are dropped.
        payload = {
            "sessionId": "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1",
            "outcome": {"result": "done"},
            "protocol_output": "proto-1",
            "classification": {"bucket": "from-axis"},
        }
        self.adapter.call_axis.return_value = {"ok": True, "status_code": 200, "data": payload}
        request_obj = {
            "operator_id": "op_999",
            "trigger": "Hello",
            "classification": "narrative",
            "next_action": "Write facts.",
            "reference": True,
            "stability": 6,
            "impact": 4,
        }
        result = self.service.execute(request_obj)
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["axis"],
            {"session_id": "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1", "outcome": {"result": "done"}, "protocol_output": "proto-1"},
        )
        self.adapter.call_axis.assert_called_once_with(
            "POST",
            "/api/v2/execute",
            "op_999",
            payload={
                "trigger": "Hello",
                "classification": "narrative",
                "next_action": "Write facts.",
                "reference": True,
                "stability": 6,
                "impact": 4,
            },
        )

    def test_old_distortion_class_field_is_rejected_before_axis(self):
        result = self.service.execute(
            {
                "operator_id": "op_999",
                "trigger": "Hello",
                "distortion_class": "narrative",
                "next_action": "Write facts.",
            }
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "validation_error")
        self.assertEqual(result["safe_details"]["field"], "axis_payload")
        # S2: caller-supplied field names are never echoed; only a count.
        self.assertEqual(result["safe_details"]["unknown_field_count"], 1)
        self.assertNotIn("distortion_class", json.dumps(result))
        self.assertNotIn("distortion_class", self.log_path.read_text(encoding="utf-8"))
        self.adapter.call_axis.assert_not_called()

    def test_gated_response_without_session_id_is_failure(self):
        # S2: gated bodies carry no verified sessionId, so they are failures
        # and their AXIS-supplied message is not passed through.
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {
                "gated": True,
                "gate_type": "breath",
                "message": "Pause and breathe.",
            },
        }
        result = self.service.execute("Need a pause", operator_id="op_111")
        self.assertFalse(result["ok"])
        self.assertNotIn("gated", result)
        self.assertEqual(result["error_type"], "axis_error")
        self.assertEqual(result["safe_details"], {"kind": "missing_session_id", "status_code": 200})
        self.assertNotIn("Pause and breathe.", json.dumps(result))

    def test_structured_axis_error_json_is_not_passed_through(self):
        # S2: AXIS's own error string and version are never returned.
        self.adapter.call_axis.return_value = {
            "ok": False,
            "status_code": 403,
            "data": {
                "ok": False,
                "error": "Guard blocked session",
                "version": "v2.3.1",
            },
        }
        result = self.service.execute("Guarded request", operator_id="op_333")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "axis_error")
        self.assertEqual(result["message"], "AXIS request failed.")
        self.assertEqual(result["safe_details"], {"kind": None, "status_code": 403})
        self.assertNotIn("Guard blocked session", json.dumps(result))
        self.assertNotIn("v2.3.1", json.dumps(result))

    def test_non_json_or_unusable_axis_error_falls_back_to_generic(self):
        self.adapter.call_axis.return_value = {
            "ok": False,
            "status_code": 500,
            "data": {"text": "<html>error</html>"},
        }
        result = self.service.execute("Server issue", operator_id="op_444")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "axis_error")
        self.assertEqual(result["message"], "AXIS request failed.")
        self.assertEqual(result["safe_details"].get("status_code"), 500)


if __name__ == "__main__":
    unittest.main()
