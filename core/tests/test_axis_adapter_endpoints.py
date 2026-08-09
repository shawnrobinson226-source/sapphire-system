"""AxisAdapter endpoint completeness: the operator-profile endpoint, the
fetch_* wrappers, and _normalize (method casing/whitespace + leading slash).

The existing suite exercises /api/v2/execute (via execute()) and /api/v2/analytics
(positive control), but never /api/v2/operator-profile, the fetch wrappers, or
_normalize directly.

Hermeticity mirrors C5: core.sapphire.axis_adapter.requests is mocked entirely
and the guard is mocked so tests never touch the network or global _system.
"""

import json
import unittest
import uuid
from pathlib import Path
from unittest import mock

from core.sapphire.axis_adapter import ALLOWED_ENDPOINTS, AxisAdapter
from core.security import violations


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


class AxisAdapterEndpointTests(unittest.TestCase):
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

    def _read_log_lines(self):
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # ---- operator-profile endpoint ----

    def test_operator_profile_is_an_allowed_endpoint(self):
        self.assertIn(("GET", "/api/v2/operator-profile"), ALLOWED_ENDPOINTS)

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_operator_profile_reaches_http_with_operator_header(self, guard, req):
        guard.return_value = (True, {})
        req.request.return_value = _FakeResponse(200, {"profile": "ok"})
        result = self.adapter.call_axis("GET", "/api/v2/operator-profile", "op_1")
        req.request.assert_called_once_with(
            "GET",
            "https://axis.example/api/v2/operator-profile",
            headers={"x-operator-id": "op_1"},
            timeout=20,
        )
        self.assertEqual(result, {"ok": True, "status_code": 200, "data": {"profile": "ok"}})
        self.assertEqual(self._read_log_lines(), [])

    # ---- fetch_* wrappers delegate to call_axis with the correct args ----

    def test_fetch_operator_profile_delegates_to_call_axis(self):
        with mock.patch.object(self.adapter, "call_axis", return_value={"ok": True}) as ca:
            result = self.adapter.fetch_operator_profile("op_1")
        ca.assert_called_once_with("GET", "/api/v2/operator-profile", "op_1")
        self.assertEqual(result, {"ok": True})

    def test_fetch_analytics_delegates_to_call_axis(self):
        with mock.patch.object(self.adapter, "call_axis", return_value={"ok": True}) as ca:
            result = self.adapter.fetch_analytics("op_1")
        ca.assert_called_once_with("GET", "/api/v2/analytics", "op_1")
        self.assertEqual(result, {"ok": True})

    # ---- _normalize edge cases ----

    def test_normalize_method_uppercased_stripped_and_none_safe(self):
        self.assertEqual(AxisAdapter._normalize("get", "/x"), ("GET", "/x"))
        self.assertEqual(AxisAdapter._normalize("  post  ", "/x"), ("POST", "/x"))
        self.assertEqual(AxisAdapter._normalize(None, "/x"), ("", "/x"))

    def test_normalize_endpoint_gets_leading_slash(self):
        self.assertEqual(
            AxisAdapter._normalize("GET", "api/v2/analytics"), ("GET", "/api/v2/analytics")
        )
        self.assertEqual(AxisAdapter._normalize("GET", "/already"), ("GET", "/already"))

    # ---- normalization is applied before both the allowlist and the request ----

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_call_axis_normalizes_method_and_endpoint_before_request(self, guard, req):
        guard.return_value = (True, {})
        req.request.return_value = _FakeResponse(200, {"ok": True})
        result = self.adapter.call_axis("get", "api/v2/analytics", "op_1")
        req.request.assert_called_once_with(
            "GET",
            "https://axis.example/api/v2/analytics",
            headers={"x-operator-id": "op_1"},
            timeout=20,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(self._read_log_lines(), [])

    @mock.patch("core.sapphire.axis_adapter.requests")
    @mock.patch("core.sapphire.axis_adapter.assert_axis_execution_allowed")
    def test_normalized_forbidden_endpoint_is_blocked_and_logged(self, guard, req):
        guard.return_value = (True, {})
        result = self.adapter.call_axis("get", "api/v2/forbidden", "op_1")
        self.assertEqual(result["violation_type"], "forbidden_endpoint")
        # Logged/returned endpoint is the normalized form.
        self.assertEqual(result["endpoint"], "GET /api/v2/forbidden")
        req.request.assert_not_called()
        lines = self._read_log_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["violation_type"], "forbidden_endpoint")
        self.assertEqual(lines[0]["endpoint"], "GET /api/v2/forbidden")


if __name__ == "__main__":
    unittest.main()
