"""S5: parallel AXIS execution paths are retired; the governed paths remain.

Retired: the axis-runtime pre_chat hook, the execute_axis dispatcher, the
fetch_axis_* model tools, CLI and SapphireUIApp direct execution, and
ExecutionService. Retained: axis_tools._execute_axis (tri flow),
axis_tools._fetch_axis_* (Test AXIS Identity), session history rendering, and
AxisAdapter as an inert reference.

Fully offline: tests/offline_guard.py's no_network fixture blocks every real
socket connect, and the transport's HTTP entry point
(core.sapphire.axis_http.requests.request) is replaced by a recording fake.
"""

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.sapphire import axis_contract, axis_http

ROOT = Path(__file__).resolve().parents[1]

_GUARD_PATH = Path(__file__).with_name("offline_guard.py")
_spec = importlib.util.spec_from_file_location("s5_offline_guard", _GUARD_PATH)
_offline_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_offline_guard)

# Registers the autouse fixture for every test in this module.
no_network = _offline_guard.no_network

OPERATOR = "op-s5"
SESSION_ID = "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1"
AXIS_BASE = "https://axis.example"
SERVICE_TOKEN = "s5-test-service-token-0123456789abcdef"


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)
        self.headers = {}

    def json(self):
        return self._body


@pytest.fixture
def axis_transport(monkeypatch):
    """Configured AXIS env with a recording fake transport; no real HTTP."""
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        if url.endswith("/api/v2/execute"):
            return FakeResponse(200, {"ok": True, "version": "v1", "data": {"ok": True, "sessionId": SESSION_ID}})
        return FakeResponse(200, {"ok": True, "version": "v1", "data": {"profile": "p"}})

    monkeypatch.setenv("AXIS_BASE_URL", AXIS_BASE)
    monkeypatch.setenv("AXIS_SERVICE_TOKEN", SERVICE_TOKEN)
    monkeypatch.delenv("VERCEL_PROTECTION_BYPASS_SECRET", raising=False)
    monkeypatch.setattr(axis_http.requests, "request", fake_request)

    from plugins.axis_integration import axis_tools

    monkeypatch.setattr(axis_tools, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))
    return calls


class _FakeDES:
    def trigger(self, payload):
        return {"show": True}

    def start(self, payload):
        return {"interaction_id": "i-1", "question": {"id": "q1", "text": "Choose one.", "options": ["a"]}}

    def answer(self, payload):
        return {"done": True, "friction_type": "information_gap", "output": {"output_type": "clarify"}}


def _tri_flow():
    """TriSystemFlow with fake DES and identity but its DEFAULT axis_executor."""
    from core.des.tri_system_flow import TriSystemFlow

    return TriSystemFlow(
        des_flow=_FakeDES(),
        health_check=lambda: {"ok": True},
        identity_resolver=lambda prompt=False: OPERATOR,
    )


# ---- retired paths ----

def test_axis_runtime_plugin_is_removed():
    assert not (ROOT / "plugins" / "axis_runtime").exists()


def test_no_tracked_plugin_registers_axis_hooks_or_tools():
    for manifest_path in sorted((ROOT / "plugins").glob("*/plugin.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        capabilities = manifest.get("capabilities", {})
        hook_files = " ".join(str(v) for v in capabilities.get("hooks", {}).values())
        tool_files = " ".join(str(v) for v in capabilities.get("tools", []))
        assert "axis" not in manifest.get("name", "").lower() or not capabilities, manifest_path
        assert "axis" not in hook_files.lower(), manifest_path
        assert "axis" not in tool_files.lower(), manifest_path


def test_axis_tools_registers_no_model_tools_or_dispatcher():
    from plugins.axis_integration import axis_tools

    for name in ("TOOLS", "AVAILABLE_FUNCTIONS", "execute"):
        assert not hasattr(axis_tools, name), name
    manifest = json.loads((ROOT / "plugins" / "axis_integration" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["capabilities"] == {}


def test_execution_service_module_is_removed():
    assert not (ROOT / "core" / "sapphire" / "execution_service.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("core.sapphire.execution_service")


def test_cli_and_ui_have_no_direct_execution():
    from core.sapphire import cli
    from ui.app import SapphireUIApp

    assert not hasattr(SapphireUIApp, "submit_trigger")
    for name in ("AxisAdapter", "ExecutionService"):
        assert not hasattr(cli, name), name
    ui_source = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert "AxisAdapter" not in ui_source and "ExecutionService" not in ui_source


def test_chat_route_has_no_axis_runtime_probe():
    source = (ROOT / "core" / "routes" / "chat.py").read_text(encoding="utf-8")
    assert "axis-runtime" not in source
    assert "axis_runtime" not in source


# ---- moved contract definitions ----

def test_remote_failure_kinds_match_transport_constants():
    expected = {
        axis_http.KIND_REDIRECT,
        axis_http.KIND_HTTP_ERROR,
        axis_http.KIND_TIMEOUT,
        axis_http.KIND_CONNECTION_ERROR,
        axis_http.KIND_NON_JSON,
        axis_http.KIND_NOT_OK,
        axis_http.KIND_AUTH_NOT_CONFIGURED,
        axis_http.KIND_BYPASS_INVALID,
        axis_http.KIND_INSECURE_TRANSPORT,
        axis_contract.KIND_MISSING_SESSION_ID,
    }
    assert axis_contract.REMOTE_FAILURE_KINDS == expected


def test_adapter_reference_uses_contract_definitions():
    from core.sapphire import axis_adapter, renderer

    assert axis_adapter.safe_status is axis_contract.safe_status
    assert axis_adapter.KIND_MISSING_SESSION_ID == axis_contract.KIND_MISSING_SESSION_ID
    assert renderer.safe_status is axis_contract.safe_status
    assert renderer.REMOTE_FAILURE_KINDS is axis_contract.REMOTE_FAILURE_KINDS


@pytest.mark.parametrize(
    "module",
    [
        "core.sapphire.renderer",
        "core.sapphire.cli",
        "core.sapphire.axis_adapter",
        "ui.views",
        "ui.components",
        "ui.app",
        "ui.tri_system_flow",
        "core.des.tri_system_flow",
        "core.des.web_tri_system",
    ],
)
def test_module_imports_cleanly_in_fresh_interpreter(module):
    """A fresh interpreter catches import-order breakage the shared test process would hide."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


# ---- governed paths still work offline ----

def test_tri_flow_default_executor_is_axis_tools_execute_axis():
    from plugins.axis_integration import axis_tools

    assert _tri_flow().axis_executor is axis_tools._execute_axis


def test_web_tri_bridge_runs_to_verified_axis_execution_offline(axis_transport):
    from core.des.web_tri_system import WebTriSystemBridge

    flows = []

    def factory():
        flows.append(_tri_flow())
        return flows[-1]

    bridge = WebTriSystemBridge(flow_factory=factory)
    assert bridge.handle("hello") is None
    assert bridge.handle("tri")
    assert bridge.handle("a")
    assert axis_transport == []  # nothing is sent before the operator confirms
    assert bridge.handle("confirm")

    assert flows[0].axis_succeeded is True
    assert len(axis_transport) == 1
    call = axis_transport[0]
    assert call["method"] == "POST"
    assert call["url"] == AXIS_BASE + "/api/v2/execute"
    assert call["allow_redirects"] is False
    assert call["headers"]["x-operator-id"] == OPERATOR
    assert set(call["json"]) <= axis_contract.AXIS_EXECUTE_FIELDS


def test_web_tri_bridge_reject_sends_nothing(axis_transport):
    from core.des.web_tri_system import WebTriSystemBridge

    bridge = WebTriSystemBridge(flow_factory=_tri_flow)
    bridge.handle("tri")
    bridge.handle("a")
    bridge.handle("reject")
    assert axis_transport == []


def test_ui_tri_flow_runs_to_verified_axis_execution_offline(axis_transport, tmp_path):
    from core.sapphire.session_service import SessionService
    from core.sapphire.session_store import SessionStore
    from ui.app import SapphireUIApp

    app = SapphireUIApp(
        session_service=SessionService(session_store=SessionStore(root_dir=tmp_path / "sessions")),
        tri_flow_factory=_tri_flow,
    )
    assert app.start_tri_flow()["type"] == "question"
    assert app.submit_tri_answer("a")["type"] == "confirm"
    assert axis_transport == []
    state = app.confirm_tri_flow()

    assert state["type"] == "axis_result"
    assert len(axis_transport) == 1
    assert axis_transport[0]["url"] == AXIS_BASE + "/api/v2/execute"
    rendered = app.render()
    assert "Status: Completed" in rendered
    assert f"Reference: {SESSION_ID}" in rendered
    assert "Submit Trigger" not in rendered


def test_existing_history_renders_in_cli_and_ui(tmp_path, monkeypatch, capsys):
    from core.sapphire import cli
    from core.sapphire.session_service import SessionService
    from core.sapphire.session_store import SessionStore
    from ui.app import SapphireUIApp

    store = SessionStore(root_dir=tmp_path / "sessions")
    service = SessionService(session_store=store)
    session_id = service.create_session(OPERATOR)["session_id"]
    service.append_to_session(
        session_id=session_id,
        execution_result={"ok": True, "axis": {"session_id": SESSION_ID, "outcome": "reduced"}},
        trigger="t",
        operator_id=OPERATOR,
    )
    service.append_to_session(
        session_id=session_id,
        execution_result={"ok": False, "error_type": "axis_error", "message": "AXIS request failed."},
        trigger="t",
        operator_id=OPERATOR,
    )

    monkeypatch.setattr(cli, "SessionStore", lambda: SessionStore(root_dir=store.root_dir))
    monkeypatch.setattr(sys, "argv", ["sapphire-cli", "--show-session", session_id])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert f"Session: {SESSION_ID}" in out
    assert "Type: axis_error" in out

    app = SapphireUIApp(session_service=service, tri_flow_factory=_tri_flow)
    assert app.select_session(OPERATOR, session_id) is True
    rendered = app.render()
    assert f"Session: {SESSION_ID}" in rendered
    assert "Type: axis_error" in rendered


def test_test_axis_identity_helper_resolves_through_strict_transport(axis_transport):
    """The settings route imports this helper by name; it must still exist and work."""
    from plugins.axis_integration import axis_tools

    helper = getattr(axis_tools, "_fetch_axis_operator_profile")
    result, ok = helper(OPERATOR)
    assert ok is True
    assert result == {"profile": "p"}
    assert len(axis_transport) == 1
    assert axis_transport[0]["method"] == "GET"
    assert axis_transport[0]["url"] == AXIS_BASE + "/api/v2/operator-profile"

    route_source = (ROOT / "core" / "routes" / "settings.py").read_text(encoding="utf-8")
    assert "from plugins.axis_integration.axis_tools import _fetch_axis_operator_profile" in route_source


def test_test_axis_identity_route_reaches_helper(axis_transport, monkeypatch):
    from fastapi.testclient import TestClient

    from core.api_fastapi import app
    from core.auth import require_login
    from core.settings_manager import settings

    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)
    monkeypatch.delenv("SAPPHIRE_OPERATOR_ID", raising=False)
    monkeypatch.setattr(
        "core.sapphire.axis_execution_guard.assert_axis_execution_allowed", lambda *a, **k: (True, {})
    )
    previous_override = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: None
    try:
        response = TestClient(app).post("/api/settings/operator-id/test-axis-identity")
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(require_login, None)
        else:
            app.dependency_overrides[require_login] = previous_override
        settings.set("OPERATOR_ID", original, persist=False)

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert [c["url"] for c in axis_transport] == [AXIS_BASE + "/api/v2/operator-profile"]
