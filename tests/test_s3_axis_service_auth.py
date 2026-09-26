"""S3: env-only AXIS service auth + Vercel protection-bypass header at the transport.

Fully offline: tests/offline_guard.py's no_network fixture (loaded by path,
since tests/ is not a package) blocks every real socket connect, and the
transport's HTTP entry point (core.sapphire.axis_http.requests.request) is
mocked. Assertions are made on the headers actually passed to it.

Credentials are marker strings; they must never appear in any result, state,
trace, gate event, session entry, boundary log, captured log, rendered output,
settings response, or exception text.
"""

import importlib.util
import json
import logging
from pathlib import Path

import pytest
import requests

from core.sapphire import axis_adapter, axis_http, cli, renderer
from core.sapphire.axis_adapter import AxisAdapter
from core.sapphire.execution_service import REMOTE_FAILURE_KINDS, ExecutionService
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore
from core.security import violations

_GUARD_PATH = Path(__file__).with_name("offline_guard.py")
_spec = importlib.util.spec_from_file_location("s3_offline_guard", _GUARD_PATH)
_offline_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_offline_guard)

# Registers the autouse fixture for every test in this module.
no_network = _offline_guard.no_network

TOKEN_ENV = "AXIS_SERVICE_TOKEN"
BYPASS_ENV = "VERCEL_PROTECTION_BYPASS_SECRET"

TOKEN = "S3-TOKEN-MARKER-0123456789abcdefghij"  # 36 chars
TOKEN_2 = "S3-TOKEN-MARKER-SECOND-0123456789abcdef"
BYPASS = "S3BYPASSMARKERabcdef0123456789"
BYPASS_2 = "S3BYPASSMARKERsecond0123456789"
MARKERS = ("S3-TOKEN-MARKER", "S3BYPASSMARKER")

AXIS_BASE = "https://axis.example"
OPERATOR = "op-s3"
SESSION_ID = "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1"
EXECUTE = "/api/v2/execute"
GET_ENDPOINTS = ("/api/v2/analytics", "/api/v2/operator-profile")
EXECUTE_PAYLOAD = {"trigger": "t", "classification": "narrative", "next_action": "write facts"}
NEW_KINDS = ("auth_not_configured", "bypass_invalid", "insecure_transport")


# ---- fixtures ----

@pytest.fixture(autouse=True)
def axis_env(monkeypatch):
    monkeypatch.setenv("AXIS_BASE_URL", AXIS_BASE)
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    monkeypatch.delenv(BYPASS_ENV, raising=False)


@pytest.fixture(autouse=True)
def violation_log(tmp_path, monkeypatch):
    path = tmp_path / "logs" / "violations.log"
    monkeypatch.setattr(violations, "VIOLATION_LOG_PATH", path)
    return path


@pytest.fixture(autouse=True)
def guards_allow(monkeypatch):
    from plugins.axis_integration import axis_tools

    monkeypatch.setattr(axis_adapter, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))
    monkeypatch.setattr(axis_tools, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))


@pytest.fixture(autouse=True)
def legacy_sessions_untouched():
    root = Path("user") / "sessions"

    def snapshot():
        if not root.exists():
            return None
        return sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in root.iterdir())

    before = snapshot()
    yield
    assert snapshot() == before


class FakeResponse:
    def __init__(self, status_code, body=None, text=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            return json.loads(self.text)
        return self._body


class FakeHTTP:
    def __init__(self, response=None, exc=None):
        self.calls = []
        self.response = response
        self.exc = exc

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.exc:
            raise self.exc
        return self.response


@pytest.fixture
def http(monkeypatch):
    def install(**kwargs):
        fake = FakeHTTP(**kwargs)
        monkeypatch.setattr(axis_http.requests, "request", fake)
        return fake

    return install


def envelope(data):
    return {"ok": True, "version": "v1", "data": data}


def ok_execute():
    return FakeResponse(200, body=envelope({"ok": True, "sessionId": SESSION_ID}))


def ok_get():
    return FakeResponse(200, body=envelope({"value": 1}))


def headers_of(call):
    return {key.lower(): value for key, value in call["headers"].items()}


def assert_no_markers(*blobs):
    for blob in blobs:
        text = blob if isinstance(blob, str) else json.dumps(blob, default=repr)
        for marker in MARKERS:
            assert marker not in text, marker


def call_transport(method, path, **kwargs):
    """request_axis must never raise; if it does, its text must carry no credential."""
    try:
        return axis_http.request_axis(method, path, headers={"x-operator-id": OPERATOR}, **kwargs)
    except Exception as exc:  # pragma: no cover - failure path
        assert_no_markers(str(exc), repr(exc))
        raise


def execute(**kwargs):
    return call_transport("POST", EXECUTE, json_body=dict(EXECUTE_PAYLOAD), **kwargs)


# ---- Authorization on execute ----

def test_execute_with_valid_token_over_https_sends_bearer(http, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    fake = http(response=ok_execute())
    result = execute()
    assert result.ok
    assert len(fake.calls) == 1
    assert fake.calls[0]["allow_redirects"] is False
    assert headers_of(fake.calls[0])["authorization"] == f"Bearer {TOKEN}"
    assert "x-vercel-protection-bypass" not in headers_of(fake.calls[0])


def test_execute_token_is_trimmed(http, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, f"  {TOKEN}\n")
    fake = http(response=ok_execute())
    assert execute().ok
    assert headers_of(fake.calls[0])["authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "a" * 31, "S3-TOKEN-MARKER-0123 456789abcdefghij", "S3-TOKEN-MARKER-0123\t456789abcdefghij",
     "S3-TOKEN-MARKER-0123\x01456789abcdefghij", "S3-TOKEN-MARKER-0123é456789abcdefghij"],
    ids=["unset", "blank", "spaces", "31-chars", "inner-space", "inner-tab", "control-char", "non-ascii"],
)
def test_execute_without_valid_token_fails_closed(http, monkeypatch, value, caplog):
    if value is not None:
        monkeypatch.setenv(TOKEN_ENV, value)
    fake = http(response=ok_execute())
    with caplog.at_level(logging.DEBUG):
        result = execute()
    assert result.kind == "auth_not_configured"
    assert result.status is None and result.data is None and result.reason is None
    assert fake.calls == []
    assert_no_markers(repr(result), caplog.text)


def test_token_of_exactly_32_chars_is_accepted(http, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, "b" * 32)
    fake = http(response=ok_execute())
    assert execute().ok
    assert headers_of(fake.calls[0])["authorization"] == "Bearer " + "b" * 32


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_get_routes_never_receive_authorization(http, monkeypatch, path):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    fake = http(response=ok_get())
    assert call_transport("GET", path).ok
    assert "authorization" not in headers_of(fake.calls[0])


def test_get_routes_do_not_require_token(http):
    fake = http(response=ok_get())
    for path in GET_ENDPOINTS:
        assert call_transport("GET", path).ok
    assert len(fake.calls) == len(GET_ENDPOINTS)
    for call in fake.calls:
        assert "authorization" not in headers_of(call)


def test_caller_supplied_credential_headers_are_discarded(http, monkeypatch):
    fake = http(response=ok_get())
    axis_http.request_axis(
        "GET",
        "/api/v2/analytics",
        headers={"x-operator-id": OPERATOR, "Authorization": "Bearer caller", "X-Vercel-Protection-Bypass": "caller"},
    )
    sent = headers_of(fake.calls[0])
    assert "authorization" not in sent and "x-vercel-protection-bypass" not in sent
    assert sent["x-operator-id"] == OPERATOR

    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(response=ok_execute())
    axis_http.request_axis(
        "POST",
        EXECUTE,
        headers={"authorization": "Bearer caller", "x-vercel-protection-bypass": "caller"},
        json_body=dict(EXECUTE_PAYLOAD),
    )
    assert fake.calls[0]["headers"] == {"Authorization": f"Bearer {TOKEN}", "x-vercel-protection-bypass": BYPASS}


# ---- bypass header ----

def test_bypass_header_on_execute_and_gets_when_set(http, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(response=ok_execute())
    assert execute().ok
    for path in GET_ENDPOINTS:
        call_transport("GET", path)
    assert len(fake.calls) == 3
    for call in fake.calls:
        assert headers_of(call)["x-vercel-protection-bypass"] == BYPASS


def test_bypass_header_absent_when_unset_or_empty(http, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    fake = http(response=ok_execute())
    execute()
    call_transport("GET", "/api/v2/analytics")
    monkeypatch.setenv(BYPASS_ENV, "")
    execute()
    call_transport("GET", "/api/v2/analytics")
    assert len(fake.calls) == 4
    for call in fake.calls:
        assert "x-vercel-protection-bypass" not in headers_of(call)


@pytest.mark.parametrize(
    "value",
    [" ", "S3BYPASSMARKER abc", "S3BYPASSMARKER\tabc", "S3BYPASSMARKER\nabc", " S3BYPASSMARKERabc",
     "S3BYPASSMARKERabc ", "S3BYPASSMARKER\x7fabc", "S3BYPASSMARKERéabc"],
    ids=["space-only", "inner-space", "tab", "newline", "leading-space", "trailing-space", "del-char", "non-ascii"],
)
@pytest.mark.parametrize("method, path", [("POST", EXECUTE), ("GET", "/api/v2/analytics")])
def test_malformed_bypass_fails_closed(http, monkeypatch, caplog, value, method, path):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, value)
    fake = http(response=ok_execute())
    with caplog.at_level(logging.DEBUG):
        body = dict(EXECUTE_PAYLOAD) if method == "POST" else None
        result = call_transport(method, path, json_body=body)
    assert result.kind == "bypass_invalid" and result.status is None
    assert fake.calls == []
    assert_no_markers(repr(result), caplog.text)


# ---- TLS rule ----

def test_http_non_loopback_is_rejected_by_axis_config_first(http, monkeypatch):
    monkeypatch.setenv("AXIS_BASE_URL", "http://axis.example")
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(response=ok_execute())
    result = execute()
    assert result.kind == "not_configured" and result.reason == "https_required"
    assert fake.calls == []


@pytest.fixture
def permissive_config(monkeypatch):
    """Simulate a loosened axis_config that lets plain HTTP to a remote host through."""

    def resolve(explicit=None):
        return "http://axis.example"

    monkeypatch.setattr(axis_http, "resolve_axis_base_url", resolve)
    monkeypatch.setattr(axis_http, "build_axis_url", lambda base, path: base + path)


def test_execute_over_insecure_transport_fails_closed(http, monkeypatch, permissive_config, caplog):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(response=ok_execute())
    with caplog.at_level(logging.DEBUG):
        result = execute()
    assert result.kind == "insecure_transport" and result.status is None
    assert fake.calls == []
    assert_no_markers(repr(result), caplog.text)


def test_get_over_insecure_transport_sends_no_credentials(http, monkeypatch, permissive_config):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(response=ok_get())
    assert call_transport("GET", "/api/v2/analytics").ok
    sent = headers_of(fake.calls[0])
    assert "authorization" not in sent and "x-vercel-protection-bypass" not in sent


@pytest.mark.parametrize("base", ["http://127.0.0.1:3000", "http://localhost:3000", "http://[::1]:3000"])
def test_loopback_http_execute_attaches_credentials(http, monkeypatch, base):
    monkeypatch.setenv("AXIS_BASE_URL", base)
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(response=ok_execute())
    assert execute().ok
    assert len(fake.calls) == 1
    assert fake.calls[0]["url"] == base + EXECUTE
    sent = headers_of(fake.calls[0])
    assert sent["authorization"] == f"Bearer {TOKEN}"
    assert sent["x-vercel-protection-bypass"] == BYPASS


def test_explicit_https_base_attaches_credentials(http, monkeypatch):
    monkeypatch.setenv("AXIS_BASE_URL", "http://axis.example")  # would be rejected
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    fake = http(response=ok_execute())
    assert execute(base_url="https://explicit.example").ok
    assert headers_of(fake.calls[0])["authorization"] == f"Bearer {TOKEN}"


# ---- AXIS auth failures and redirects ----

@pytest.mark.parametrize(
    "status, body", [(401, {"error": "unauthorized"}), (503, {"error": "service_unavailable"})]
)
def test_axis_auth_failures_are_http_error_with_status(http, monkeypatch, status, body):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    fake = http(response=FakeResponse(status, body=body))
    result = execute()
    assert result.kind == "http_error" and result.status == status and result.data is None
    assert len(fake.calls) == 1

    adapter_result = AxisAdapter().call_axis("POST", EXECUTE, OPERATOR, payload=dict(EXECUTE_PAYLOAD))
    assert adapter_result == {"ok": False, "status_code": status, "error": "http_error"}


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_with_credentials_is_not_followed(http, monkeypatch, status):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(response=FakeResponse(status, text="", headers={"Location": "https://sso.example/login"}))
    result = execute()
    assert result.kind == "redirect" and result.status == status
    assert len(fake.calls) == 1
    assert fake.calls[0]["allow_redirects"] is False


# ---- request-time reads ----

def test_credentials_are_read_at_request_time(http, monkeypatch):
    fake = http(response=ok_execute())
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    assert execute().ok
    monkeypatch.setenv(TOKEN_ENV, TOKEN_2)
    monkeypatch.setenv(BYPASS_ENV, BYPASS_2)
    assert execute().ok
    assert headers_of(fake.calls[0])["authorization"] == f"Bearer {TOKEN}"
    assert headers_of(fake.calls[1])["authorization"] == f"Bearer {TOKEN_2}"
    assert headers_of(fake.calls[0])["x-vercel-protection-bypass"] == BYPASS
    assert headers_of(fake.calls[1])["x-vercel-protection-bypass"] == BYPASS_2

    monkeypatch.delenv(TOKEN_ENV)
    assert execute().kind == "auth_not_configured"
    monkeypatch.delenv(BYPASS_ENV)
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    assert execute().ok
    assert "x-vercel-protection-bypass" not in headers_of(fake.calls[2])
    assert len(fake.calls) == 3


# ---- no credential leaks ----

LEAK_CASES = [
    ("success", {"response": ok_execute()}),
    ("401", {"response": FakeResponse(401, body={"error": "unauthorized"})}),
    ("302", {"response": FakeResponse(302, text="", headers={"Location": "https://sso.example"})}),
    ("timeout", {"exc": requests.Timeout(f"t {TOKEN} {BYPASS}")}),
    ("conn", {"exc": requests.ConnectionError(f"c Authorization: Bearer {TOKEN} {BYPASS}")}),
    ("invalid-header", {"exc": requests.exceptions.InvalidHeader(f"bad {BYPASS}")}),
]


@pytest.mark.parametrize("case", [c[1] for c in LEAK_CASES], ids=[c[0] for c in LEAK_CASES])
def test_transport_adapter_and_tools_never_leak_credentials(http, monkeypatch, caplog, case):
    from plugins.axis_integration import axis_tools

    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    http(**case)
    with caplog.at_level(logging.DEBUG):
        transport = execute()
        adapter = AxisAdapter().call_axis("POST", EXECUTE, OPERATOR, payload=dict(EXECUTE_PAYLOAD))
        get = AxisAdapter().fetch_analytics(OPERATOR)
        tools = axis_tools._execute_axis(trigger="t", operator_id=OPERATOR, classification="narrative",
                                         next_action="n")
        tools_get = axis_tools._fetch_axis_analytics(OPERATOR)
    assert_no_markers(repr(transport), adapter, get, tools, tools_get, caplog.text)


@pytest.fixture
def service_env(tmp_path):
    store = SessionStore(root_dir=tmp_path / "sessions")
    session_service = SessionService(session_store=store)
    service = ExecutionService(axis_adapter=AxisAdapter(), session_service=session_service)
    session = session_service.create_session(OPERATOR)
    return service, session_service, session["session_id"], store


@pytest.mark.parametrize("case", [c[1] for c in LEAK_CASES], ids=[c[0] for c in LEAK_CASES])
def test_execution_service_sessions_logs_and_rendering_never_leak(
    http, monkeypatch, caplog, violation_log, service_env, case
):
    from ui.views import render_history_entry, render_result

    service, session_service, session_id, _ = service_env
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    http(**case)
    with caplog.at_level(logging.DEBUG):
        result = service.execute("t", operator_id=OPERATOR, session_id=session_id)
    stored = session_service.get_session(session_id)
    rendered = [render_result(result)] + [render_history_entry(e) for e in stored["entries"]]
    log = violation_log.read_text(encoding="utf-8") if violation_log.exists() else ""
    assert_no_markers(result, stored, log, caplog.text, *rendered)


def test_execution_service_contains_foreign_exception_text(http, monkeypatch, violation_log, service_env):
    service, session_service, session_id, _ = service_env
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    http(exc=RuntimeError(f"unexpected {TOKEN}"))
    result = service.execute("t", operator_id=OPERATOR, session_id=session_id)
    assert result["ok"] is False
    log = violation_log.read_text(encoding="utf-8") if violation_log.exists() else ""
    assert_no_markers(result, session_service.get_session(session_id), log)


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_new_kinds_surface_through_service_and_renderer(http, monkeypatch, violation_log, service_env, kind):
    service, session_service, session_id, _ = service_env
    fake = http(response=ok_execute())
    if kind == "auth_not_configured":
        pass  # token unset
    elif kind == "bypass_invalid":
        monkeypatch.setenv(TOKEN_ENV, TOKEN)
        monkeypatch.setenv(BYPASS_ENV, "S3BYPASSMARKER bad")
    else:
        monkeypatch.setenv(TOKEN_ENV, TOKEN)
        monkeypatch.setattr(axis_http, "resolve_axis_base_url", lambda explicit=None: "http://axis.example")
        monkeypatch.setattr(axis_http, "build_axis_url", lambda base, path: base + path)
    result = service.execute("t", operator_id=OPERATOR, session_id=session_id)
    assert fake.calls == []
    assert result == {
        "ok": False,
        "error_type": "axis_error",
        "message": "AXIS request failed.",
        "safe_details": {"kind": kind, "status_code": None},
    }
    assert kind in REMOTE_FAILURE_KINDS
    text = renderer.render_failure(result)
    assert f"Kind: {kind}" in text
    stored = session_service.get_session(session_id)["entries"]
    assert len(stored) == 1 and stored[0]["result_type"] == "failure"
    assert_no_markers(result, stored, violation_log.read_text(encoding="utf-8"), text)


def test_renderer_drops_kinds_outside_allowlist():
    text = renderer.render_failure(
        {"ok": False, "error_type": "axis_error", "safe_details": {"kind": f"Bearer {TOKEN}", "status_code": None}}
    )
    assert "Kind:" not in text
    assert_no_markers(text)


def test_cli_output_never_contains_credentials(http, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    http(response=FakeResponse(401, body={"error": "unauthorized"}))
    monkeypatch.setattr(cli, "SessionStore", lambda: SessionStore(root_dir=tmp_path / "sessions"))
    for extra in ([], ["--json"]):
        monkeypatch.setattr("sys.argv", ["sapphire-cli", "t", "--operator-id", OPERATOR, *extra])
        assert cli.main() == 0
    out = capsys.readouterr().out
    assert "Kind: http_error" in out and "Status: 401" in out
    assert_no_markers(out)

    monkeypatch.delenv(TOKEN_ENV)
    monkeypatch.setattr("sys.argv", ["sapphire-cli", "t", "--operator-id", OPERATOR])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "Kind: auth_not_configured" in out
    assert_no_markers(out)


# ---- tri-system flow ----

class _FakeDES:
    def trigger(self, payload):
        return {"show": True}

    def start(self, payload):
        return {"interaction_id": "i-1", "question": {"id": "q1", "text": "Choose one.", "options": ["a"]}}

    def answer(self, payload):
        return {"done": True, "friction_type": "information_gap", "output": {"output_type": "clarify"}}


def _flow():
    from core.des.tri_system_flow import TriSystemFlow

    flow = TriSystemFlow(
        des_flow=_FakeDES(),
        health_check=lambda: {"ok": True},
        identity_resolver=lambda prompt=False: OPERATOR,
    )
    flow.start()
    assert flow.submit_answer("a")["type"] == "result"
    return flow


def _set_kind_env(monkeypatch, kind):
    if kind == "bypass_invalid":
        monkeypatch.setenv(TOKEN_ENV, TOKEN)
        monkeypatch.setenv(BYPASS_ENV, "S3BYPASSMARKER bad")
    elif kind == "insecure_transport":
        monkeypatch.setenv(TOKEN_ENV, TOKEN)
        monkeypatch.setenv(BYPASS_ENV, BYPASS)
        monkeypatch.setattr(axis_http, "resolve_axis_base_url", lambda explicit=None: "http://axis.example")
        monkeypatch.setattr(axis_http, "build_axis_url", lambda base, path: base + path)
    else:
        monkeypatch.setenv(BYPASS_ENV, BYPASS)


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_tri_flow_surfaces_new_kinds_as_themselves(http, monkeypatch, caplog, kind):
    from core.des.tri_system_flow import AXIS_FAILURE_KINDS
    from ui.views import render_tri_state

    assert kind in AXIS_FAILURE_KINDS
    _set_kind_env(monkeypatch, kind)
    fake = http(response=ok_execute())
    flow = _flow()
    with caplog.at_level(logging.DEBUG):
        state = flow.confirm()
    assert fake.calls == []
    assert state["type"] == "error"
    assert state["data"]["detail"] == {"error": kind, "status_code": None}
    assert state["data"]["message"] == "AXIS execution failed."
    assert flow.axis_attempted is True and flow.axis_succeeded is False
    assert [e["step"] for e in flow.get_trace()][-1] == "AXIS_REJECTED"
    rendered = render_tri_state(state)
    assert "AXIS execution failed." in rendered
    assert_no_markers(state, flow.get_trace(), flow.get_gate_events(), rendered, caplog.text)


@pytest.mark.parametrize("case", [c[1] for c in LEAK_CASES], ids=[c[0] for c in LEAK_CASES])
def test_tri_flow_state_trace_and_gate_events_never_leak(http, monkeypatch, caplog, case):
    from core.des.web_tri_system import WebTriSystemBridge
    from ui.views import render_tri_state

    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    fake = http(**case)
    flow = _flow()
    with caplog.at_level(logging.DEBUG):
        state = flow.confirm()
    assert len(fake.calls) == 1
    assert headers_of(fake.calls[0])["authorization"] == f"Bearer {TOKEN}"
    assert_no_markers(state, flow.get_trace(), flow.get_gate_events(), render_tri_state(state), caplog.text)

    bridge = WebTriSystemBridge(flow_factory=lambda: _flow_unstarted())
    outputs = [bridge.handle("tri"), bridge.handle("a"), bridge.handle("confirm")]
    assert_no_markers(*[o for o in outputs if o])


def _flow_unstarted():
    from core.des.tri_system_flow import TriSystemFlow

    return TriSystemFlow(
        des_flow=_FakeDES(),
        health_check=lambda: {"ok": True},
        identity_resolver=lambda prompt=False: OPERATOR,
    )


def test_tri_flow_unknown_executor_kind_still_generic(http):
    from core.des.tri_system_flow import TriSystemFlow

    flow = TriSystemFlow(
        des_flow=_FakeDES(),
        health_check=lambda: {"ok": True},
        identity_resolver=lambda prompt=False: OPERATOR,
        axis_executor=lambda **kwargs: ({"error": f"Bearer {TOKEN}", "status_code": None}, False),
    )
    flow.start()
    flow.submit_answer("a")
    state = flow.confirm()
    assert state["data"]["detail"] == {"error": "axis_failed", "status_code": None}
    assert_no_markers(state)


# ---- settings never expose the env vars ----

@pytest.fixture
def settings_client(monkeypatch):
    from fastapi.testclient import TestClient

    from core.api_fastapi import app
    from core.auth import require_login

    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    monkeypatch.setenv(BYPASS_ENV, BYPASS)
    app.dependency_overrides[require_login] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_login, None)


def test_settings_endpoints_never_expose_env_credentials(settings_client):
    from core.settings_manager import settings

    settings.reload()  # re-applies the env override list with the markers set
    response = settings_client.get("/api/settings")
    assert response.status_code == 200
    body = response.text
    for needle in (TOKEN_ENV, BYPASS_ENV, TOKEN, BYPASS):
        assert needle not in body
    keys = list(response.json()["settings"])
    assert TOKEN_ENV not in keys and BYPASS_ENV not in keys

    for key in keys:
        single = settings_client.get(f"/api/settings/{key}")
        for needle in (TOKEN_ENV, BYPASS_ENV, TOKEN, BYPASS):
            assert needle not in single.text, key

    # Requesting the env var names directly: not a setting, value never returned.
    for name in (TOKEN_ENV, BYPASS_ENV):
        single = settings_client.get(f"/api/settings/{name}")
        assert single.status_code == 404
        assert TOKEN not in single.text and BYPASS not in single.text
