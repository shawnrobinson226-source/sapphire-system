"""AxisAdapter.call_axis fail-closed branches: zero_tools_mode and
invalid_operator_id (transport-layer guards).

These two branches were untested at the transport chokepoint. Neither may
issue an HTTP request. Behavior differs on logging, confirmed against source:
  - invalid_operator_id  -> writes one violation-log entry (payload redacted
    via the _payload_snapshot contract already proven in
    test_violation_log_redaction.py, C2) and returns a boundary_failure
  - zero_tools_mode      -> returns a boundary_failure but writes NO log line
    (it fails closed silently; see the observation flagged for C5)

Hermeticity: core.sapphire.axis_adapter.requests is mocked entirely and the
guard (assert_axis_execution_allowed) is mocked so tests never depend on global
_system state or the real network. A positive-control test proves a valid call
does reach requests, so the not-called assertions are meaningful.
"""

import json
import unittest
import uuid
from pathlib import Path
from unittest import mock

from core.sapphire.axis_adapter import AxisAdapter
from core.security import violations


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


class AxisAdapterFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.log_path = self.tmp_root / "logs" / "sapphire_boundary_violations.log"
        patch = mock.patch.object(violations, "VIOLATION_LOG_PATH", self.log_path)
        patch.start()
        self.addCleanup(patch.stop)
        self.adapter = AxisAdapter(axis_base_url="https://axis.example")

    def _cleanup_tmp_root(self):
        if not self.tmp_root.exists():
            return
        for path in sorted(self.tmp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.tmp_root.rmdir()

    def _read_raw(self):
        if not self.log_path.exists():
            return ""
        return self.log_path.read_text(encoding="utf-8")

    def _read_log_lines(self):
        return [json.loads(line) for line in self._read_raw().splitlines() if line.strip()]

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_zero_tools_mode_blocks_without_http_or_log(self, guard, req):
        guard.return_value = (
            False,
            {"error": "AXIS execution blocked because Zero tools mode is active."},
        )
        result = self.adapter.call_axis(
            "POST", "/api/v2/execute", "op_123", payload={"trigger": "SECRET-TRIGGER"}
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "boundary_violation")
        self.assertEqual(result["violation_type"], "zero_tools_mode")
        self.assertEqual(
            result["message"], "AXIS execution blocked because Zero tools mode is active."
        )
        self.assertEqual(result["endpoint"], "POST /api/v2/execute")
        self.assertEqual(result["operator_id"], "op_123")
        # The in-memory return dict passes the payload through raw under
        # "payload_snapshot" (this branch writes nothing to disk). Redaction
        # applies on the persisted log path, exercised in the invalid-op test.
        self.assertEqual(result["payload_snapshot"], {"trigger": "SECRET-TRIGGER"})
        req.request.assert_not_called()
        # zero_tools_mode fails closed WITHOUT writing a violation-log entry.
        self.assertEqual(self._read_log_lines(), [])

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_zero_tools_mode_nulls_blank_operator_id_in_result(self, guard, req):
        guard.return_value = (False, {"error": "blocked"})
        result = self.adapter.call_axis("POST", "/api/v2/execute", "   ")
        self.assertEqual(result["violation_type"], "zero_tools_mode")
        self.assertIsNone(result["operator_id"])
        req.request.assert_not_called()

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_invalid_operator_id_blocks_logs_and_makes_no_http_call(self, guard, req):
        guard.return_value = (True, {"zero_tools_mode": False})
        result = self.adapter.call_axis(
            "POST", "/api/v2/execute", "", payload={"trigger": "SECRET-TRIGGER"}
        )
        # Returned boundary_failure shape.
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "boundary_violation")
        self.assertEqual(result["violation_type"], "invalid_operator_id")
        self.assertEqual(result["message"], "operator_id must be a non-empty string.")
        self.assertEqual(result["endpoint"], "POST /api/v2/execute")
        self.assertIsNone(result["operator_id"])
        self.assertIsNone(result["payload_snapshot"])
        # No HTTP call escapes this branch.
        req.request.assert_not_called()
        # Exactly one violation-log line, correct type, operator_id nulled.
        lines = self._read_log_lines()
        self.assertEqual(len(lines), 1)
        entry = lines[0]
        self.assertEqual(entry["violation_type"], "invalid_operator_id")
        self.assertEqual(entry["endpoint"], "POST /api/v2/execute")
        self.assertIsNone(entry["operator_id"])
        # Payload redacted via the C2-proven _payload_snapshot contract: value
        # shapes only, and the raw trigger never reaches the log file.
        self.assertEqual(entry["payload_snapshot"]["value_shapes"]["trigger"]["type"], "str")
        self.assertNotIn("SECRET-TRIGGER", self._read_raw())

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_invalid_operator_id_variants_all_fail_closed(self, guard, req):
        guard.return_value = (True, {})
        for bad in ("", "   ", None, 123):
            result = self.adapter.call_axis("GET", "/api/v2/analytics", bad)
            self.assertEqual(result["violation_type"], "invalid_operator_id", bad)
            self.assertIsNone(result["operator_id"])
        req.request.assert_not_called()

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_valid_call_reaches_http_and_writes_no_violation_log(self, guard, req):
        # Positive control: guard allows + endpoint allowed + operator valid ->
        # requests IS called, so the not-called assertions above are meaningful.
        guard.return_value = (True, {})
        req.request.return_value = _FakeResponse(200, {"ok": True})
        result = self.adapter.call_axis("GET", "/api/v2/analytics", "op_123")
        req.request.assert_called_once()
        _, kwargs = req.request.call_args
        self.assertEqual(kwargs["headers"]["x-operator-id"], "op_123")
        self.assertTrue(result["ok"])
        self.assertEqual(self._read_log_lines(), [])


if __name__ == "__main__":
    unittest.main()
