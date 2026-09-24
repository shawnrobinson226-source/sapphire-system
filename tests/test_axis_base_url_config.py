"""AXIS base-URL configuration: one validator, resolved only at the request boundary."""

import json
import sys

import pytest

from core.sapphire import axis_adapter, axis_config, cli
from core.sapphire.axis_adapter import ALLOWED_ENDPOINTS, AxisAdapter
from core.sapphire.axis_config import (
    AxisConfigError,
    build_axis_url,
    resolve_axis_base_url,
    validate_axis_base_url,
)
from core.sapphire.execution_service import ExecutionService
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore
from core.security import violations


class _FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data if data is not None else {"ok": True}
        self.ok = 200 <= status_code < 300
        self.text = json.dumps(self._data)

    def json(self):
        return self._data


@pytest.fixture
def no_axis_env(monkeypatch):
    monkeypatch.delenv("AXIS_BASE_URL", raising=False)


@pytest.fixture
def violation_log(tmp_path, monkeypatch):
    path = tmp_path / "logs" / "violations.log"
    monkeypatch.setattr(violations, "VIOLATION_LOG_PATH", path)
    return path


@pytest.fixture
def adapter_requests(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return _FakeResponse(200, {"ok": True})

    monkeypatch.setattr(axis_adapter.requests, "request", fake_request)
    monkeypatch.setattr(axis_adapter, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))
    return calls


# ---- validator: accepted values ----

@pytest.mark.parametrize(
    "value, expected",
    [
        ("https://axis.example", "https://axis.example"),
        ("https://axis.example/", "https://axis.example"),
        ("https://axis.example:8443", "https://axis.example:8443"),
        ("HTTPS://axis.example", "https://axis.example"),
        ("  https://axis.example  ", "https://axis.example"),
        ("http://localhost:3000", "http://localhost:3000"),
        ("http://127.0.0.1:3000/", "http://127.0.0.1:3000"),
        ("http://[::1]:3000", "http://[::1]:3000"),
    ],
)
def test_valid_base_urls_normalize_to_scheme_and_host(value, expected):
    assert validate_axis_base_url(value) == expected


# ---- validator: rejected values ----

@pytest.mark.parametrize(
    "value, reason",
    [
        (None, "missing"),
        ("", "missing"),
        ("   ", "missing"),
        ("axis.example", "invalid_scheme"),
        ("ftp://axis.example", "invalid_scheme"),
        ("https://", "missing_host"),
        ("https://axis.example:notaport", "invalid_port"),
        ("https://user:pw@axis.example", "credentials_not_allowed"),
        ("https://user@axis.example", "credentials_not_allowed"),
        ("https://axis.example?x=1", "query_or_fragment_not_allowed"),
        ("https://axis.example/?", "query_or_fragment_not_allowed"),
        ("https://axis.example#frag", "query_or_fragment_not_allowed"),
        ("https://axis.example/api/v2", "path_not_allowed"),
        ("https://axis.example/api/v2/execute", "path_not_allowed"),
        ("https://axis.example//", "path_not_allowed"),
        ("http://axis.example", "https_required"),
        ("http://192.168.1.50:3000", "https_required"),
        ("http://0.0.0.0:3000", "https_required"),
        ("https://axis .example", "whitespace_not_allowed"),
    ],
)
def test_invalid_base_urls_are_rejected_with_reason(value, reason):
    with pytest.raises(AxisConfigError) as excinfo:
        validate_axis_base_url(value)
    assert excinfo.value.reason == reason


@pytest.mark.parametrize(
    "value",
    [
        "https://user:s3cr3t-pw@axis.example",
        "https://axis.example/?token=s3cr3t-pw",
        "http://s3cr3t-pw.internal.example",
        "https://s3cr3t-pw.example/api/v2",
    ],
)
def test_error_messages_never_echo_the_configured_value(value):
    with pytest.raises(AxisConfigError) as excinfo:
        validate_axis_base_url(value)
    assert "s3cr3t-pw" not in str(excinfo.value)
    assert value.strip() not in str(excinfo.value)


def test_missing_message_names_the_environment_variable():
    with pytest.raises(AxisConfigError) as excinfo:
        validate_axis_base_url(None)
    assert "AXIS_BASE_URL" in str(excinfo.value)


# ---- resolution and composition ----

def test_resolve_prefers_explicit_value_over_environment(monkeypatch):
    monkeypatch.setenv("AXIS_BASE_URL", "https://env.example")
    assert resolve_axis_base_url("https://explicit.example") == "https://explicit.example"
    assert resolve_axis_base_url() == "https://env.example"


def test_resolve_without_environment_is_missing(no_axis_env):
    with pytest.raises(AxisConfigError) as excinfo:
        resolve_axis_base_url()
    assert excinfo.value.reason == "missing"


@pytest.mark.parametrize("path", sorted({endpoint for _, endpoint in ALLOWED_ENDPOINTS}))
@pytest.mark.parametrize("base", ["https://axis.example", "https://axis.example/"])
def test_allowlisted_paths_are_appended_exactly_once(base, path):
    url = build_axis_url(base, path)
    assert url == f"https://axis.example{path}"
    assert url.count("/api/v2/") == 1


def test_build_rejects_non_api_v2_paths():
    with pytest.raises(ValueError):
        build_axis_url("https://axis.example", "/other")


def test_no_hardcoded_axis_destination_remains():
    assert not hasattr(axis_config, "DEFAULT_AXIS_BASE_URL")
    from plugins.axis_integration import axis_tools

    assert not hasattr(axis_tools, "BASE_URL")


# ---- AxisAdapter / ExecutionService ----

def test_adapter_construction_does_not_require_configuration(no_axis_env):
    AxisAdapter()
    AxisAdapter(axis_base_url="not a url")


def test_adapter_missing_config_returns_axis_not_configured_without_request(
    no_axis_env, violation_log, adapter_requests
):
    result = AxisAdapter().call_axis("GET", "/api/v2/analytics", "op_1")
    assert result["ok"] is False
    assert result["error"] == "axis_not_configured"
    assert result["reason"] == "missing"
    assert adapter_requests == []


def test_adapter_uses_environment_base_url(monkeypatch, violation_log, adapter_requests):
    monkeypatch.setenv("AXIS_BASE_URL", "https://axis.example/")
    result = AxisAdapter().call_axis("GET", "/api/v2/operator-profile", "op_1")
    assert result["ok"] is True
    assert adapter_requests[0]["url"] == "https://axis.example/api/v2/operator-profile"


def test_adapter_explicit_invalid_url_is_rejected_without_request(
    no_axis_env, violation_log, adapter_requests
):
    result = AxisAdapter(axis_base_url="http://axis.example").call_axis(
        "GET", "/api/v2/analytics", "op_1"
    )
    assert result["error"] == "axis_not_configured"
    assert result["reason"] == "https_required"
    assert "axis.example" not in result["message"]
    assert adapter_requests == []


def test_adapter_zero_tools_guard_precedes_url_resolution(no_axis_env, violation_log, monkeypatch):
    monkeypatch.setattr(
        axis_adapter,
        "assert_axis_execution_allowed",
        lambda *a, **k: (False, {"error": "AXIS execution blocked because Zero tools mode is active."}),
    )
    result = AxisAdapter().call_axis("GET", "/api/v2/analytics", "op_1")
    assert result["error"] == "boundary_violation"
    assert result["violation_type"] == "zero_tools_mode"


def test_adapter_allowlist_precedes_url_resolution(no_axis_env, violation_log, adapter_requests):
    result = AxisAdapter().call_axis("GET", "/api/v2/forbidden", "op_1")
    assert result["error"] == "boundary_violation"
    assert result["violation_type"] == "forbidden_endpoint"


def test_adapter_operator_identity_precedes_url_resolution(no_axis_env, violation_log, adapter_requests):
    result = AxisAdapter().call_axis("GET", "/api/v2/analytics", "   ")
    assert result["error"] == "boundary_violation"
    assert result["violation_type"] == "invalid_operator_id"


def test_execution_service_reports_axis_not_configured_not_axis_error(
    tmp_path, monkeypatch, violation_log, adapter_requests
):
    secret_url = "http://s3cr3t-host.example"
    monkeypatch.setenv("AXIS_BASE_URL", secret_url)
    service = ExecutionService(
        axis_adapter=AxisAdapter(),
        session_service=SessionService(session_store=SessionStore(root_dir=tmp_path / "sessions")),
    )

    result = service.execute("trigger text", operator_id="op_1")

    assert result["ok"] is False
    assert result["error_type"] == "axis_not_configured"
    assert result["safe_details"] == {"reason": "https_required"}
    assert adapter_requests == []
    assert "s3cr3t-host" not in json.dumps(result)
    assert "s3cr3t-host" not in violation_log.read_text(encoding="utf-8")


# ---- axis_tools (plugin + tri-system + settings path) ----

@pytest.fixture
def axis_tools_module(monkeypatch):
    from plugins.axis_integration import axis_tools

    calls = []
    monkeypatch.setattr(axis_tools, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))
    monkeypatch.setattr(axis_tools.requests, "get", lambda *a, **k: calls.append((a, k)) or _FakeResponse())
    monkeypatch.setattr(axis_tools.requests, "post", lambda *a, **k: calls.append((a, k)) or _FakeResponse())
    return axis_tools, calls


def test_axis_tools_missing_config_fails_clearly_without_request(no_axis_env, axis_tools_module):
    axis_tools, calls = axis_tools_module
    result, ok = axis_tools._fetch_axis_operator_profile("op_1")
    assert ok is False
    assert result["error"] == "axis_not_configured"
    assert result["reason"] == "missing"
    assert calls == []


def test_axis_tools_composes_endpoint_under_api_v2_once(monkeypatch, axis_tools_module):
    axis_tools, calls = axis_tools_module
    monkeypatch.setenv("AXIS_BASE_URL", "https://axis.example/")
    result, ok = axis_tools._fetch_axis_operator_profile("op_1")
    assert ok is True
    assert calls[0][0][0] == "https://axis.example/api/v2/operator-profile"


def test_axis_tools_guard_precedes_url_resolution(no_axis_env, monkeypatch):
    from plugins.axis_integration import axis_tools

    blocked = {"error": "AXIS execution blocked because Zero tools mode is active."}
    monkeypatch.setattr(axis_tools, "assert_axis_execution_allowed", lambda *a, **k: (False, blocked))
    result, ok = axis_tools._fetch_axis_analytics("op_1")
    assert ok is False
    assert result == blocked


def test_axis_tools_operator_check_precedes_url_resolution(no_axis_env, axis_tools_module):
    axis_tools, calls = axis_tools_module
    result, ok = axis_tools._fetch_axis_analytics("  ")
    assert ok is False
    assert result == {"error": "A non-empty 'operator_id' is required."}
    assert calls == []


class _FakeDES:
    def trigger(self, payload):
        return {"show": True}

    def start(self, payload):
        return {"interaction_id": "i-1", "question": {"id": "q1", "text": "Choose one.", "options": ["a"]}}

    def answer(self, payload):
        return {"done": True, "friction_type": "information_gap", "output": {"output_type": "clarify"}}


def _tri_flow(**kwargs):
    from core.des.tri_system_flow import TriSystemFlow

    return TriSystemFlow(
        des_flow=_FakeDES(),
        health_check=lambda: {"ok": True},
        identity_resolver=lambda prompt=False: "operator-1",
        **kwargs,
    )


def test_tri_flow_reports_axis_not_configured_through_default_executor(no_axis_env, axis_tools_module):
    _, calls = axis_tools_module
    flow = _tri_flow()
    flow.start()
    flow.submit_answer("a")

    state = flow.confirm()

    assert state["type"] == "error"
    assert state["data"]["message"] == "AXIS is not configured. Execution stopped."
    assert state["data"]["detail"]["error"] == "axis_not_configured"
    assert calls == []


def test_settings_identity_test_reports_blocked_not_offline_when_unconfigured(
    no_axis_env, axis_tools_module, monkeypatch
):
    from fastapi.testclient import TestClient

    from core.api_fastapi import app
    from core.auth import require_login
    from core.sapphire import axis_execution_guard
    from core.settings_manager import settings

    _, calls = axis_tools_module
    monkeypatch.delenv("SAPPHIRE_OPERATOR_ID", raising=False)
    monkeypatch.setattr(axis_execution_guard, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))
    app.dependency_overrides[require_login] = lambda: None
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)
    try:
        response = TestClient(app).post("/api/settings/operator-id/test-axis-identity")
    finally:
        settings.set("OPERATOR_ID", original, persist=False)

    assert response.status_code == 200
    assert response.json() == {"status": "blocked", "reason": "axis_not_configured"}
    assert calls == []


# ---- non-AXIS operations work without AXIS_BASE_URL ----

def test_ui_app_constructs_and_runs_non_axis_operations_without_config(
    tmp_path, no_axis_env, violation_log, adapter_requests
):
    from ui.app import SapphireUIApp

    app = SapphireUIApp(
        session_service=SessionService(session_store=SessionStore(root_dir=tmp_path / "sessions")),
        tri_flow_factory=lambda: _tri_flow(axis_executor=lambda **k: ({"ok": True}, True)),
    )

    session_id = app.create_new_session("op_1")
    assert app.select_session("op_1", session_id) is True
    assert app.show_session(session_id) == []
    assert app.start_tri_flow()["type"] == "question"

    result = app.submit_trigger("trigger text")
    assert result["error_type"] == "axis_not_configured"
    assert adapter_requests == []


def _run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["sapphire-cli", *args])
    code = cli.main()
    return code, capsys.readouterr().out


def test_cli_session_commands_work_without_config(
    tmp_path, monkeypatch, capsys, no_axis_env, violation_log, adapter_requests
):
    monkeypatch.chdir(tmp_path)
    code, out = _run_cli(monkeypatch, capsys, "--new-session", "--operator-id", "op_1")
    session_id = out.strip()
    assert code == 0 and session_id

    code, out = _run_cli(monkeypatch, capsys, "--show-session", session_id, "--json")
    assert code == 0
    assert json.loads(out)["session_id"] == session_id
    assert adapter_requests == []


def test_cli_execute_without_config_fails_clearly_without_request(
    tmp_path, monkeypatch, capsys, no_axis_env, violation_log, adapter_requests
):
    monkeypatch.chdir(tmp_path)
    code, out = _run_cli(monkeypatch, capsys, "trigger text", "--operator-id", "op_1", "--json")
    assert json.loads(out)["error_type"] == "axis_not_configured"
    assert adapter_requests == []


def test_cli_explicit_axis_base_url_is_validated_and_used(
    tmp_path, monkeypatch, capsys, no_axis_env, violation_log, adapter_requests
):
    monkeypatch.chdir(tmp_path)
    _, out = _run_cli(
        monkeypatch, capsys, "t", "--operator-id", "op_1", "--json", "--axis-base-url", "http://axis.example"
    )
    assert json.loads(out)["safe_details"] == {"reason": "https_required"}
    assert adapter_requests == []

    _run_cli(
        monkeypatch, capsys, "t", "--operator-id", "op_1", "--json", "--axis-base-url", "https://axis.example/"
    )
    assert adapter_requests[0]["url"] == "https://axis.example/api/v2/execute"
