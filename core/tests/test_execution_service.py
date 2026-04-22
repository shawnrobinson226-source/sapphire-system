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
        self.adapter.call_axis.return_value = {
            "ok": True,
            "status_code": 200,
            "data": {
                "classification": {"label": "x"},
                "protocol": {"name": "p"},
                "steps": [{"id": "s1"}, {"id": "s2"}],
                "outcome": {"status": "ok"},
                "continuity": {"id": "c1"},
            },
        }
        result = self.service.execute("Ship patch", operator_id="op_123")
        self.assertTrue(result["ok"])
        self.assertEqual(result["axis"]["classification"], {"label": "x"})
        self.assertEqual(result["axis"]["protocol"], {"name": "p"})
        self.assertEqual(result["axis"]["action"], {"id": "s1"})
        self.assertEqual(result["axis"]["outcome"], {"status": "ok"})
        self.assertEqual(result["axis"]["continuity"], {"id": "c1"})
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
        payload = {
            "classification": {"bucket": "from-axis"},
            "protocol": {"id": "proto-1"},
            "action": {"type": "next-step"},
            "outcome": {"result": "done"},
            "continuity": {"token": "abc"},
        }
        self.adapter.call_axis.return_value = {"ok": True, "status_code": 200, "data": payload}
        request_obj = {"operator_id": "op_999", "trigger": "Hello", "client_tag": "abc123"}
        result = self.service.execute(request_obj)
        self.assertTrue(result["ok"])
        self.assertEqual(result["axis"]["classification"], payload["classification"])
        self.assertEqual(result["axis"]["protocol"], payload["protocol"])
        self.assertEqual(result["axis"]["action"], payload["action"])
        self.assertEqual(result["axis"]["outcome"], payload["outcome"])
        self.assertEqual(result["axis"]["continuity"], payload["continuity"])
        self.adapter.call_axis.assert_called_once_with(
            "POST",
            "/api/v2/execute",
            "op_999",
            payload={"trigger": "Hello", "client_tag": "abc123"},
        )

    def test_gated_success_passes_through_gate_shape(self):
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
        self.assertTrue(result["ok"])
        self.assertTrue(result["gated"])
        self.assertEqual(result["gate_type"], "breath")
        self.assertEqual(result["message"], "Pause and breathe.")


if __name__ == "__main__":
    unittest.main()
