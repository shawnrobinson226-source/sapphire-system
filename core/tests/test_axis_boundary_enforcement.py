import json
import unittest
import uuid
from pathlib import Path
from unittest import mock

from core.sapphire import distortion_lock
from core.sapphire.axis_adapter import AxisAdapter
from core.security import violations


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class AxisBoundaryEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.log_path = self.tmp_root / "logs" / "sapphire_boundary_violations.log"
        self.violations_patch = mock.patch.object(violations, "VIOLATION_LOG_PATH", self.log_path)
        self.violations_patch.start()
        self.addCleanup(self.violations_patch.stop)
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

    def _read_log_lines(self):
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @mock.patch("core.sapphire.axis_adapter.requests.request")
    def test_allowed_endpoints_pass(self, mock_request):
        mock_request.return_value = _FakeResponse(200, {"ok": True})
        result = self.adapter.call_axis("GET", "/api/v2/analytics", operator_id="op_123")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        self.assertEqual(kwargs["headers"]["x-operator-id"], "op_123")

    @mock.patch("core.sapphire.axis_adapter.requests.request")
    def test_forbidden_endpoints_fail(self, mock_request):
        with self.assertRaises(ValueError):
            self.adapter.call_axis("GET", "/api/v2/forbidden", operator_id="op_123")
        mock_request.assert_not_called()
        logs = self._read_log_lines()
        self.assertEqual(logs[-1]["reason"], "forbidden_endpoint")

    def test_distortion_class_sync_passes(self):
        source = self.tmp_root / "distortion-types.ts"
        classes = ", ".join(f"'{c}'" for c in distortion_lock.ALLOWED_DISTORTION_CLASSES)
        source.write_text(
            "export const DISTORTION_CLASS_VERSION = "
            f"'{distortion_lock.DISTORTION_CLASS_VERSION}';\n"
            f"export const DISTORTION_TYPES = [{classes}];\n",
            encoding="utf-8",
        )
        self.assertTrue(distortion_lock.assert_distortion_sync(source))

    def test_distortion_class_sync_fails(self):
        source = self.tmp_root / "distortion-types.ts"
        source.write_text(
            "export const DISTORTION_CLASS_VERSION = 'axis-v2-locked';\n"
            "export const DISTORTION_TYPES = ['behavioral', 'cognitive'];\n",
            encoding="utf-8",
        )
        with self.assertRaises(RuntimeError):
            distortion_lock.assert_distortion_sync(source)

    def test_log_separation_is_enforced(self):
        entry = violations.log_boundary_violation(
            reason="test_boundary",
            endpoint="GET /api/v2/forbidden",
            payload={"foo": "bar"},
        )
        self.assertEqual(self.log_path.name, "sapphire_boundary_violations.log")
        self.assertEqual(self.log_path.parent.name, "logs")
        logs = self._read_log_lines()
        self.assertEqual(logs[-1]["reason"], entry["reason"])

    @mock.patch("core.sapphire.axis_adapter.requests.request")
    def test_adapter_does_not_call_unknown_routes(self, mock_request):
        with self.assertRaises(ValueError):
            self.adapter.call_axis("POST", "/api/v2/anything-else", operator_id="op_123", payload={"x": 1})
        mock_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
