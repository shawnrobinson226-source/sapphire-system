"""S2: AxisAdapter on the strict transport; ExecutionService consumes only verified results.

Fully offline: tests/offline_guard.py's no_network fixture (loaded by path,
since tests/ is not a package) blocks every real socket connect, and the
transport's HTTP entry point (core.sapphire.axis_http.requests.request) is
mocked. Response shapes follow the AXIS v1 contract (ok/version/data envelope;
401/503 bodies without ok/version).

Every SessionStore here uses a temporary root; the default user/sessions store
is never touched.
"""

import importlib.util
import json
import logging
import socket
import threading
from pathlib import Path

import pytest
import requests

from core.sapphire import axis_adapter, axis_contract, axis_http, cli, renderer
from core.sapphire.axis_adapter import AxisAdapter, safe_status
from core.sapphire.execution_service import ExecutionService
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore
from core.security import violations

_GUARD_PATH = Path(__file__).with_name("offline_guard.py")
_spec = importlib.util.spec_from_file_location("s2_offline_guard", _GUARD_PATH)
_offline_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_offline_guard)

# Registers the autouse fixture for every test in this module.
no_network = _offline_guard.no_network

AXIS_BASE = "https://secret-host-marker.example"
EXPLICIT_BASE = "https://explicit-base.example"
BODY_MARKER = "SECRET-BODY-MARKER"
EXC_MARKER = "SECRET-EXC-MARKER"
AXIS_ERR_MARKER = "SECRET-AXIS-ERROR-MARKER"
OPERATOR = "op-SECRET-OPERATOR-MARKER"
KEY_MARKER = "SECRET-KEY-MARKER"
VALUE_MARKER = "SECRET-VALUE-MARKER"
ENDPOINT_MARKER = "SECRET-ENDPOINT-MARKER"
LOCATION_MARKER = "secret-location-marker"
SESSION_ID = "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1"

MARKERS = (
    "secret-host-marker",
    BODY_MARKER,
    EXC_MARKER,
    AXIS_ERR_MARKER,
    OPERATOR,
    KEY_MARKER,
    VALUE_MARKER,
    ENDPOINT_MARKER,
    LOCATION_MARKER,
)

TRIGGER = "trigger text"
EXECUTE_PAYLOAD = {"trigger": TRIGGER, "classification": "narrative", "next_action": "write facts"}


# ---- fixtures ----

@pytest.fixture(autouse=True)
def axis_env(monkeypatch):
    monkeypatch.setenv("AXIS_BASE_URL", AXIS_BASE)
    # S3: execute fails closed without a service token; bypass stays unset.
    monkeypatch.setenv("AXIS_SERVICE_TOKEN", "test-service-token-0123456789abcdef")
    monkeypatch.delenv("VERCEL_PROTECTION_BYPASS_SECRET", raising=False)


@pytest.fixture(autouse=True)
def violation_log(tmp_path, monkeypatch):
    path = tmp_path / "logs" / "violations.log"
    monkeypatch.setattr(violations, "VIOLATION_LOG_PATH", path)
    return path


@pytest.fixture(autouse=True)
def guard_allows(monkeypatch):
    calls = []

    def allow(path, *args, **kwargs):
        calls.append(path)
        return True, {}

    monkeypatch.setattr(axis_adapter, "assert_axis_execution_allowed", allow)
    return calls


@pytest.fixture(autouse=True)
def legacy_sessions_untouched():
    """The default store (user/sessions) must be neither created nor modified."""
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
            return json.loads(self.text)  # raises ValueError (JSONDecodeError) for HTML etc.
        return self._body


class FakeHTTP:
    """Records calls to axis_http.requests.request and replays one response."""

    def __init__(self, response=None, exc=None, handler=None):
        self.calls = []
        self.response = response
        self.exc = exc
        self.handler = handler

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.handler:
            return self.handler(method, url, **kwargs)
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


@pytest.fixture
def store(tmp_path):
    return SessionStore(root_dir=tmp_path / "sessions")


@pytest.fixture
def service_env(store):
    session_service = SessionService(session_store=store)
    service = ExecutionService(axis_adapter=AxisAdapter(), session_service=session_service)
    session = session_service.create_session(OPERATOR)
    return service, session_service, session["session_id"]


def envelope(data):
    return {"ok": True, "version": "v1", "data": data}


def error_envelope(error):
    return {"ok": False, "version": "v1", "error": error}


def verified_data():
    return {
        "ok": True,
        "sessionId": SESSION_ID,
        "outcome": "reduced",
        "clarity_rating": 7,
        "steps_completed": 3,
        "continuity_before": 40,
        "continuity_after": 55,
        "protocol_output": "done",
    }


def html(status=200):
    return FakeResponse(status, text=f"<html><body>Vercel SSO login {BODY_MARKER}</body></html>")


def redirect(status):
    return FakeResponse(
        status,
        text=f"Redirecting {BODY_MARKER}",
        headers={"Location": f"https://{LOCATION_MARKER}.example/sso?next={BODY_MARKER}"},
    )


def assert_no_markers(*blobs):
    for blob in blobs:
        text = blob if isinstance(blob, str) else json.dumps(blob, default=repr)
        for marker in MARKERS:
            assert marker not in text, marker


def log_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def entries(session_service, session_id):
    return session_service.get_session(session_id)["entries"]


# ---- offline guard is loaded and active ----

def test_offline_guard_is_loaded_from_tests_dir():
    assert Path(_offline_guard.__file__).resolve() == _GUARD_PATH.resolve()
    assert _GUARD_PATH.parent.name == "tests"


@pytest.mark.parametrize("target", [("127.0.0.1", 8000), ("127.0.0.1", 9), ("localhost", 80)])
def test_ordinary_socket_connect_is_blocked(target):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(AssertionError, match=_offline_guard.NETWORK_BLOCKED_MESSAGE):
            sock.connect(target)
        with pytest.raises(AssertionError, match=_offline_guard.NETWORK_BLOCKED_MESSAGE):
            sock.connect_ex(target)


def test_guarded_socketpair_still_works_and_clears_flag():
    left, right = socket.socketpair()
    try:
        left.sendall(b"ping")
        assert right.recv(4) == b"ping"
    finally:
        left.close()
        right.close()
    assert not getattr(_offline_guard.SOCKETPAIR_GUARD, "active", False)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(AssertionError):
            sock.connect(("127.0.0.1", 8000))


def test_forced_fallback_socketpair_works_only_inside_the_guard(no_network, monkeypatch):
    """Windows code path: route the wrapper to Python's _fallback_socketpair."""
    fallback = getattr(socket, "_fallback_socketpair", None)
    if fallback is None:
        pytest.skip("this Python has no socket._fallback_socketpair")
    calls = []

    def counting_fallback(*args, **kwargs):
        calls.append(threading.get_ident())
        return fallback(*args, **kwargs)

    monkeypatch.setattr(no_network, "impl", counting_fallback)
    assert socket.socketpair is no_network.wrapper

    left, right = socket.socketpair()
    try:
        left.sendall(b"ping")
        assert right.recv(4) == b"ping"
    finally:
        left.close()
        right.close()
    assert calls == [threading.get_ident()]
    assert not getattr(_offline_guard.SOCKETPAIR_GUARD, "active", False)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(AssertionError, match=_offline_guard.NETWORK_BLOCKED_MESSAGE):
            sock.connect(("127.0.0.1", 8000))


# ---- shared execute contract ----

@pytest.mark.parametrize(
    "data, expected",
    [
        ({"sessionId": SESSION_ID}, True),
        ({"sessionId": " x "}, True),
        ({"sessionId": ""}, False),
        ({"sessionId": "   "}, False),
        ({"sessionId": 123}, False),
        ({"sessionId": None}, False),
        ({}, False),
        ([SESSION_ID], False),
        (None, False),
    ],
)
def test_execute_contract_rule(data, expected):
    from plugins.axis_integration import axis_tools

    assert axis_contract.has_execute_session_id(data) is expected
    assert axis_tools.has_execute_session_id(data) is expected


@pytest.mark.parametrize("value, expected", [(200, 200), (100, 100), (599, 599), (99, None), (600, None),
                                             (True, None), ("200", None), (None, None), (200.0, None)])
def test_safe_status(value, expected):
    assert safe_status(value) == expected


# ---- remote failures: adapter and ExecutionService ----

SSO_302 = redirect(302)

FAILURE_CASES = [
    # id, response kwargs, expected kind, expected status
    ("redirect_301", {"response": redirect(301)}, "redirect", 301),
    ("redirect_302", {"response": SSO_302}, "redirect", 302),
    ("redirect_303", {"response": redirect(303)}, "redirect", 303),
    ("redirect_307", {"response": redirect(307)}, "redirect", 307),
    ("html_200", {"response": html(200)}, "non_json", 200),
    ("malformed_json", {"response": FakeResponse(200, text='{"ok": true, ' + BODY_MARKER)}, "non_json", 200),
    ("json_array", {"response": FakeResponse(200, body=[BODY_MARKER, SESSION_ID])}, "non_json", 200),
    ("ok_missing", {"response": FakeResponse(200, body={"version": "v1", "data": {"sessionId": SESSION_ID}})},
     "not_ok", 200),
    ("ok_false", {"response": FakeResponse(200, body=error_envelope(AXIS_ERR_MARKER))}, "not_ok", 200),
    ("data_missing", {"response": FakeResponse(200, body={"ok": True, "version": "v1"})}, "not_ok", 200),
    ("data_not_dict", {"response": FakeResponse(200, body={"ok": True, "version": "v1", "data": [SESSION_ID]})},
     "not_ok", 200),
    ("session_id_missing", {"response": FakeResponse(200, body=envelope({"ok": True, "outcome": BODY_MARKER}))},
     "missing_session_id", 200),
    ("session_id_empty", {"response": FakeResponse(200, body=envelope({"sessionId": "", "outcome": "x"}))},
     "missing_session_id", 200),
    ("session_id_blank", {"response": FakeResponse(200, body=envelope({"sessionId": "   "}))},
     "missing_session_id", 200),
    ("session_id_non_string", {"response": FakeResponse(200, body=envelope({"sessionId": 12345}))},
     "missing_session_id", 200),
    ("gated_without_session_id",
     {"response": FakeResponse(200, body=envelope({"gated": True, "gate_type": "breath", "message": AXIS_ERR_MARKER}))},
     "missing_session_id", 200),
    ("http_401_no_envelope", {"response": FakeResponse(401, body={"error": AXIS_ERR_MARKER})}, "http_error", 401),
    ("http_503_no_envelope", {"response": FakeResponse(503, body={"error": AXIS_ERR_MARKER})}, "http_error", 503),
    ("http_400_guard_blocked", {"response": FakeResponse(400, body=error_envelope("guard_blocked"))},
     "http_error", 400),
    ("http_400", {"response": FakeResponse(400, body=error_envelope(AXIS_ERR_MARKER))}, "http_error", 400),
    ("http_403", {"response": FakeResponse(403, body=error_envelope(AXIS_ERR_MARKER))}, "http_error", 403),
    ("http_405", {"response": FakeResponse(405, text=BODY_MARKER)}, "http_error", 405),
    ("http_429", {"response": FakeResponse(429, body=error_envelope(AXIS_ERR_MARKER))}, "http_error", 429),
    ("http_500", {"response": html(500)}, "http_error", 500),
    ("timeout", {"exc": requests.Timeout(f"{EXC_MARKER} {AXIS_BASE}")}, "timeout", None),
    ("connection_error", {"exc": requests.ConnectionError(f"{EXC_MARKER} {AXIS_BASE}")}, "connection_error", None),
]


@pytest.mark.parametrize(
    "kwargs, kind, status", [c[1:] for c in FAILURE_CASES], ids=[c[0] for c in FAILURE_CASES]
)
def test_adapter_remote_failure_is_controlled(kwargs, kind, status, http, violation_log, caplog):
    fake = http(**kwargs)
    with caplog.at_level(logging.DEBUG):
        result = AxisAdapter().call_axis("POST", "/api/v2/execute", OPERATOR, payload=dict(EXECUTE_PAYLOAD))

    assert result == {"ok": False, "status_code": status, "error": kind}
    assert len(fake.calls) == 1
    assert fake.calls[0]["allow_redirects"] is False
    assert_no_markers(result, log_text(violation_log), caplog.text)


@pytest.mark.parametrize(
    "kwargs, kind, status", [c[1:] for c in FAILURE_CASES], ids=[c[0] for c in FAILURE_CASES]
)
def test_service_remote_failure_is_controlled(kwargs, kind, status, http, service_env, violation_log, caplog):
    service, session_service, session_id = service_env
    fake = http(**kwargs)
    with caplog.at_level(logging.DEBUG):
        result = service.execute(TRIGGER, operator_id=OPERATOR, session_id=session_id)

    assert result == {
        "ok": False,
        "error_type": "axis_error",
        "message": "AXIS request failed.",
        "safe_details": {"kind": kind, "status_code": status},
    }
    assert len(fake.calls) == 1
    assert fake.calls[0]["allow_redirects"] is False

    stored = entries(session_service, session_id)
    assert len(stored) == 1
    assert stored[0]["result_type"] == "failure"
    assert stored[0]["axis"] == {}
    assert stored[0]["failure"] == {"error_type": "axis_error", "message": "AXIS request failed."}
    assert_no_markers(result, stored, log_text(violation_log), caplog.text)


def test_sso_redirect_chain_is_never_followed_or_success(http, service_env, violation_log):
    """If the redirect were followed, the chain would end in a 'successful' envelope."""
    service, session_service, session_id = service_env

    def handler(method, url, **kwargs):
        if kwargs.get("allow_redirects", True):
            return FakeResponse(200, body=envelope(verified_data()))
        return SSO_302

    fake = http(handler=handler)
    adapter_result = AxisAdapter().call_axis("POST", "/api/v2/execute", OPERATOR, payload=dict(EXECUTE_PAYLOAD))
    service_result = service.execute(TRIGGER, operator_id=OPERATOR, session_id=session_id)

    assert adapter_result == {"ok": False, "status_code": 302, "error": "redirect"}
    assert service_result["ok"] is False
    assert service_result["safe_details"] == {"kind": "redirect", "status_code": 302}
    assert len(fake.calls) == 2
    assert all(call["allow_redirects"] is False for call in fake.calls)
    assert [e["result_type"] for e in entries(session_service, session_id)] == ["failure"]


# ---- configuration ----

def test_missing_base_url_makes_zero_requests(monkeypatch, http, service_env, violation_log):
    monkeypatch.delenv("AXIS_BASE_URL", raising=False)
    service, session_service, session_id = service_env
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))

    adapter_result = AxisAdapter().call_axis("POST", "/api/v2/execute", OPERATOR, payload=dict(EXECUTE_PAYLOAD))
    service_result = service.execute(TRIGGER, operator_id=OPERATOR, session_id=session_id)

    assert fake.calls == []
    assert adapter_result["ok"] is False
    assert adapter_result["error"] == "axis_not_configured"
    assert adapter_result["reason"] == "missing"
    assert adapter_result["status_code"] is None
    assert service_result["error_type"] == "axis_not_configured"
    assert service_result["safe_details"] == {"reason": "missing"}
    assert [e["result_type"] for e in entries(session_service, session_id)] == ["failure"]
    assert_no_markers(adapter_result, service_result, log_text(violation_log))


def test_explicit_base_url_is_honored_over_environment(http):
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    result = AxisAdapter(axis_base_url=EXPLICIT_BASE).call_axis(
        "POST", "/api/v2/execute", OPERATOR, payload=dict(EXECUTE_PAYLOAD)
    )
    assert result["ok"] is True
    assert fake.calls[0]["url"] == EXPLICIT_BASE + "/api/v2/execute"


def test_ui_app_explicit_base_url_reaches_transport(http, store):
    from ui.app import SapphireUIApp

    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    app = SapphireUIApp(
        axis_base_url=EXPLICIT_BASE,
        session_service=SessionService(session_store=store),
        tri_flow_factory=lambda: None,
    )
    app.create_new_session(OPERATOR)
    result = app.submit_trigger(TRIGGER)

    assert result["ok"] is True
    assert len(fake.calls) == 1
    assert fake.calls[0]["url"] == EXPLICIT_BASE + "/api/v2/execute"
    assert fake.calls[0]["allow_redirects"] is False


# ---- verified success ----

def test_adapter_verified_success_returns_validated_data(http):
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    result = AxisAdapter().call_axis("POST", "/api/v2/execute", OPERATOR, payload=dict(EXECUTE_PAYLOAD))

    assert result == {"ok": True, "status_code": 200, "data": verified_data()}
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == AXIS_BASE + "/api/v2/execute"
    assert call["json"] == EXECUTE_PAYLOAD
    assert call["headers"] == {
        "x-operator-id": OPERATOR,
        "Content-Type": "application/json",
        "Authorization": "Bearer test-service-token-0123456789abcdef",
    }
    assert call["allow_redirects"] is False


def test_service_verified_success_appends_exactly_one_success(http, service_env, violation_log):
    service, session_service, session_id = service_env
    data = dict(verified_data(), classification=BODY_MARKER, extra={"x": BODY_MARKER})
    http(response=FakeResponse(200, body=envelope(data)))

    result = service.execute(TRIGGER, operator_id=OPERATOR, session_id=session_id)

    assert result == {
        "ok": True,
        "axis": {
            "session_id": SESSION_ID,
            "outcome": "reduced",
            "clarity_rating": 7,
            "steps_completed": 3,
            "continuity_before": 40,
            "continuity_after": 55,
            "protocol_output": "done",
        },
        "pipeline": {"source": "axis_adapter", "status_code": 200},
    }
    stored = entries(session_service, session_id)
    assert len(stored) == 1
    assert stored[0]["result_type"] == "success"
    assert stored[0]["axis"] == result["axis"]
    assert stored[0]["trigger"] == TRIGGER
    assert_no_markers(result, stored, log_text(violation_log))


def test_service_success_copies_only_present_contract_fields(http, service_env):
    service, _, _ = service_env
    http(response=FakeResponse(200, body=envelope({"sessionId": f"  {SESSION_ID}  "})))
    result = service.execute(TRIGGER, operator_id=OPERATOR)
    assert result["ok"] is True
    assert result["axis"] == {"session_id": SESSION_ID}


def test_service_rejects_adapter_success_without_session_id():
    """Defense in depth: a (mocked) adapter claiming ok without sessionId is not success."""

    class LyingAdapter:
        def call_axis(self, *args, **kwargs):
            return {"ok": True, "status_code": 200, "data": {"outcome": BODY_MARKER}}

    result = ExecutionService(axis_adapter=LyingAdapter()).execute(TRIGGER, operator_id=OPERATOR)
    assert result["ok"] is False
    assert result["safe_details"] == {"kind": "missing_session_id", "status_code": 200}
    assert_no_markers(result)


def test_service_unexpected_exception_is_generic(service_env, violation_log):
    _, session_service, session_id = service_env

    class ExplodingAdapter:
        def call_axis(self, *args, **kwargs):
            raise RuntimeError(f"{EXC_MARKER} {AXIS_BASE}")

    service = ExecutionService(axis_adapter=ExplodingAdapter(), session_service=session_service)
    result = service.execute(TRIGGER, operator_id=OPERATOR, session_id=session_id)

    assert result == {
        "ok": False,
        "error_type": "axis_error",
        "message": "AXIS request failed unexpectedly.",
        "safe_details": {"exception_type": "RuntimeError"},
    }
    assert entries(session_service, session_id) == []
    assert_no_markers(result, log_text(violation_log))


# ---- local guards: zero requests, no echo ----

def test_forbidden_endpoint_makes_zero_requests_and_is_generic(http, violation_log, guard_allows):
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    result = AxisAdapter().call_axis(
        f"GET-{ENDPOINT_MARKER}", f"/api/v2/{ENDPOINT_MARKER}", OPERATOR, payload={KEY_MARKER: VALUE_MARKER}
    )
    assert fake.calls == []
    assert result == {
        "ok": False,
        "status_code": None,
        "error": "boundary_violation",
        "violation_type": "forbidden_endpoint",
        "message": "Endpoint not allowed.",
        "endpoint": None,
    }
    assert guard_allows == ["axis_adapter.forbidden_endpoint"]
    assert "forbidden_endpoint" in log_text(violation_log)
    assert_no_markers(result, log_text(violation_log))


def test_zero_tools_blocks_with_zero_requests_and_no_echo(monkeypatch, http, violation_log):
    monkeypatch.setattr(
        axis_adapter,
        "assert_axis_execution_allowed",
        lambda *a, **k: (False, {"error": "blocked", "path": ENDPOINT_MARKER, "operator": OPERATOR}),
    )
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    payload = dict(EXECUTE_PAYLOAD, next_action=VALUE_MARKER, **{KEY_MARKER: VALUE_MARKER})

    result = AxisAdapter().call_axis("POST", "/api/v2/execute", OPERATOR, payload=payload)

    assert fake.calls == []
    assert result == {
        "ok": False,
        "status_code": None,
        "error": "boundary_violation",
        "violation_type": "zero_tools_mode",
        "message": "AXIS execution blocked because Zero tools mode is active.",
        "endpoint": "POST /api/v2/execute",
    }
    assert_no_markers(result, log_text(violation_log))


def test_zero_tools_blocks_service_with_no_success_entry(monkeypatch, http, service_env, violation_log):
    service, session_service, session_id = service_env
    monkeypatch.setattr(axis_adapter, "assert_axis_execution_allowed", lambda *a, **k: (False, {"error": "x"}))
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))

    result = service.execute(
        {"trigger": TRIGGER, "operator_id": OPERATOR, "next_action": VALUE_MARKER}, session_id=session_id
    )

    assert fake.calls == []
    assert result["error_type"] == "boundary_violation"
    assert result["safe_details"] == {"violation_type": "zero_tools_mode", "endpoint": "POST /api/v2/execute"}
    stored = entries(session_service, session_id)
    assert [e["result_type"] for e in stored] == ["failure"]
    assert_no_markers(result, stored, log_text(violation_log))


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_invalid_operator_id_makes_zero_requests(bad, http, violation_log):
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    payload = {"trigger": TRIGGER, KEY_MARKER: VALUE_MARKER}
    result = AxisAdapter().call_axis("POST", "/api/v2/execute", bad, payload=payload)

    assert fake.calls == []
    assert result["error"] == "boundary_violation"
    assert result["violation_type"] == "invalid_operator_id"
    assert "operator_id" not in result
    assert_no_markers(result, log_text(violation_log))


def test_service_missing_operator_id_makes_zero_requests(http, violation_log):
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    result = ExecutionService(axis_adapter=AxisAdapter()).execute({"trigger": VALUE_MARKER})
    assert fake.calls == []
    assert result["error_type"] == "validation_error"
    assert_no_markers(result, log_text(violation_log))


def test_adapter_unknown_payload_field_makes_zero_requests(http, violation_log):
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    payload = dict(EXECUTE_PAYLOAD, **{KEY_MARKER: VALUE_MARKER})
    result = AxisAdapter().call_axis("POST", "/api/v2/execute", OPERATOR, payload=payload)

    assert fake.calls == []
    assert result["violation_type"] == "invalid_payload"
    log = log_text(violation_log)
    assert '"unknown_field_count"' in log
    assert_no_markers(result, log)


def test_adapter_get_with_payload_makes_zero_requests(http, violation_log):
    fake = http(response=FakeResponse(200, body=envelope({})))
    result = AxisAdapter().call_axis("GET", "/api/v2/analytics", OPERATOR, payload={KEY_MARKER: VALUE_MARKER})
    assert fake.calls == []
    assert result["violation_type"] == "invalid_payload"
    assert_no_markers(result, log_text(violation_log))


def test_service_unknown_payload_field_makes_zero_requests(http, service_env, violation_log):
    service, session_service, session_id = service_env
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    result = service.execute(
        {"trigger": TRIGGER, "operator_id": OPERATOR, KEY_MARKER: VALUE_MARKER}, session_id=session_id
    )

    assert fake.calls == []
    assert result == {
        "ok": False,
        "error_type": "validation_error",
        "message": "Request contains fields outside the AXIS contract.",
        "safe_details": {"field": "axis_payload", "unknown_field_count": 1},
    }
    assert entries(session_service, session_id) == []
    assert_no_markers(result, log_text(violation_log))


def test_adapter_execute_classification_lock_makes_zero_requests(http, violation_log):
    fake = http(response=FakeResponse(200, body=envelope(verified_data())))
    result = AxisAdapter().execute(
        trigger=TRIGGER, classification=VALUE_MARKER, next_action="x", operator_id=OPERATOR
    )
    assert fake.calls == []
    assert result["violation_type"] == "invalid_distortion_class"
    assert_no_markers(result, log_text(violation_log))


def test_get_endpoints_use_envelope_rule_only(http):
    fake = http(response=FakeResponse(200, body=envelope({"profile": "p"})))
    assert AxisAdapter().fetch_operator_profile(OPERATOR) == {"ok": True, "status_code": 200, "data": {"profile": "p"}}
    http(response=redirect(302))
    assert AxisAdapter().fetch_analytics(OPERATOR) == {"ok": False, "status_code": 302, "error": "redirect"}
    assert fake.calls[0]["allow_redirects"] is False


# ---- rendering: new, legacy success, legacy gated ----

def test_contract_success_renders_scalars_only():
    output = renderer.render_success(
        {
            "ok": True,
            "axis": {
                "session_id": SESSION_ID,
                "outcome": "reduced",
                "clarity_rating": 7,
                "steps_completed": {"nested": BODY_MARKER},
                "continuity_before": True,
                "continuity_after": float("nan"),
                "protocol_output": [BODY_MARKER],
            },
        }
    )
    assert output.splitlines() == [
        "=== AXIS RESULT ===",
        f"Session: {SESSION_ID}",
        "Outcome: reduced",
        "Clarity Rating: 7",
        "Steps Completed: N/A",
        "Continuity Before: N/A",
        "Continuity After: N/A",
        "Protocol Output: N/A",
    ]
    assert BODY_MARKER not in output


def _legacy_entries():
    return [
        {
            "timestamp": "t1",
            "trigger": "old",
            "axis": {
                "classification": "stable",
                "protocol": {"steps": ["a", "b"]},
                "action": "a",
                "outcome": "ok",
                "continuity": "c-1",
            },
            "result_type": "success",
        },
        {
            "timestamp": "t2",
            "trigger": "old",
            "axis": {},
            "gated": {"gate_type": "breath", "message": AXIS_ERR_MARKER},
            "result_type": "gated",
        },
    ]


def test_legacy_entries_render_in_ui_without_stored_gated_message(store):
    from ui.views import render_history_entry

    success, gated = (render_history_entry(e) for e in _legacy_entries())
    assert "Classification: stable" in success
    assert "1. a" in success
    assert gated.endswith("=== SYSTEM PAUSE === " + renderer.LEGACY_PAUSE_MESSAGE)
    assert AXIS_ERR_MARKER not in gated


def test_legacy_entries_render_in_cli_without_stored_gated_message(tmp_path, monkeypatch, capsys, store):
    session = store.create_session(OPERATOR)
    for entry in _legacy_entries():
        store.append_entry(session["session_id"], entry)
    monkeypatch.setattr(cli, "SessionStore", lambda: SessionStore(root_dir=store.root_dir))
    monkeypatch.setattr("sys.argv", ["sapphire-cli", "--show-session", session["session_id"]])

    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "Classification: stable" in out
    assert renderer.LEGACY_PAUSE_MESSAGE in out
    assert AXIS_ERR_MARKER not in out


# ---- amendment: sink-level redaction ----

def _log_entries(path):
    return [json.loads(line) for line in log_text(path).splitlines() if line.strip()]


def test_sink_never_writes_operator_id_value(violation_log):
    violations.log_boundary_violation(violation_type="t", endpoint="POST /api/v2/execute", operator_id=OPERATOR)
    for absent in (None, "", "   "):
        violations.log_boundary_violation(violation_type="t", operator_id=absent)

    entries_ = _log_entries(violation_log)
    assert [e["operator_id_present"] for e in entries_] == [True, False, False, False]
    assert all("operator_id" not in e for e in entries_)
    assert_no_markers(log_text(violation_log))


def test_sink_never_writes_caller_field_names(violation_log):
    payload = {
        KEY_MARKER: VALUE_MARKER,
        "trigger": VALUE_MARKER,
        "nested": {KEY_MARKER + "-2": [VALUE_MARKER, {KEY_MARKER + "-3": 1}]},
    }
    entry = violations.log_boundary_violation(
        violation_type="t", payload=payload, details={KEY_MARKER: VALUE_MARKER, "kind": "timeout"}
    )

    snapshot = entry["payload_snapshot"]
    assert snapshot["size"] == 3
    assert snapshot["keys"] == ["trigger"]
    assert snapshot["value_shapes"] == {"trigger": {"type": "str", "length": len(VALUE_MARKER)}}
    assert snapshot["other_key_count"] == 2
    nested = snapshot["other_value_shapes"][1]
    assert nested["other_key_count"] == 1
    assert nested["other_value_shapes"][0]["type"] == "list"
    assert entry["details"]["keys"] == ["kind"]
    assert entry["details"]["other_key_count"] == 1
    assert _log_entries(violation_log)[-1] == entry
    assert_no_markers(log_text(violation_log))


def test_sink_fixed_labels_cover_axis_execute_fields():
    assert axis_contract.AXIS_EXECUTE_FIELDS <= violations.SAFE_KEY_LABELS


# ---- amendment: failure rendering ----

LEGACY_FAILURE_ENTRY = {
    "timestamp": "t3",
    "trigger": "old",
    "axis": {},
    "failure": {
        "error_type": "axis_error",
        "message": f"{AXIS_ERR_MARKER} {BODY_MARKER} {AXIS_BASE}",
        "safe_details": {"kind": AXIS_ERR_MARKER, "status_code": BODY_MARKER, "version": EXC_MARKER},
    },
    "result_type": "failure",
}
LEGACY_UNKNOWN_FAILURE_ENTRY = {
    "timestamp": "t4",
    "trigger": "old",
    "axis": {},
    "failure": {"error_type": f"type-{KEY_MARKER}", "message": EXC_MARKER},
    "result_type": "failure",
}


def test_legacy_failure_entries_render_in_ui_without_markers():
    from ui.views import render_history_entry

    known = render_history_entry(LEGACY_FAILURE_ENTRY)
    unknown = render_history_entry(LEGACY_UNKNOWN_FAILURE_ENTRY)
    assert known.splitlines()[1:] == [
        "=== EXECUTION FAILURE ===",
        "Type: axis_error",
        "Message: AXIS request failed.",
    ]
    assert unknown.splitlines()[1:] == [
        "=== EXECUTION FAILURE ===",
        "Type: unknown",
        "Message: Execution failed.",
    ]
    assert_no_markers(known, unknown)


def test_legacy_failure_entries_render_in_cli_without_markers(monkeypatch, capsys, store):
    session = store.create_session(OPERATOR)
    store.append_entry(session["session_id"], LEGACY_FAILURE_ENTRY)
    store.append_entry(session["session_id"], LEGACY_UNKNOWN_FAILURE_ENTRY)
    monkeypatch.setattr(cli, "SessionStore", lambda: SessionStore(root_dir=store.root_dir))
    monkeypatch.setattr("sys.argv", ["sapphire-cli", "--show-session", session["session_id"]])

    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "Message: AXIS request failed." in out
    assert "Message: Execution failed." in out
    assert_no_markers(out)


@pytest.mark.parametrize(
    "error_type, text",
    [
        ("validation_error", "Request failed validation."),
        ("boundary_violation", "Request rejected by AXIS boundary rules."),
        ("axis_not_configured", "AXIS is not configured."),
        ("axis_error", "AXIS request failed."),
    ],
)
def test_failure_types_render_fixed_text(error_type, text):
    output = renderer.render_failure({"ok": False, "error_type": error_type, "message": BODY_MARKER})
    assert output == f"=== EXECUTION FAILURE ===\nType: {error_type}\nMessage: {text}"


def test_new_remote_failure_renders_allowlisted_kind_and_valid_status(http, service_env):
    from ui.views import render_result

    service, _, session_id = service_env
    http(response=FakeResponse(403, body=error_envelope(AXIS_ERR_MARKER)))
    output = render_result(service.execute(TRIGGER, operator_id=OPERATOR, session_id=session_id))

    assert output.splitlines() == [
        "=== EXECUTION FAILURE ===",
        "Type: axis_error",
        "Message: AXIS request failed.",
        "Kind: http_error",
        "Status: 403",
    ]
    assert_no_markers(output)


@pytest.mark.parametrize("status", [None, 0, 99, 600, True, "403", 403.0])
def test_failure_rendering_omits_invalid_status_and_unknown_kind(status):
    output = renderer.render_failure(
        {"ok": False, "error_type": "axis_error", "safe_details": {"kind": BODY_MARKER, "status_code": status}}
    )
    assert output == "=== EXECUTION FAILURE ===\nType: axis_error\nMessage: AXIS request failed."
