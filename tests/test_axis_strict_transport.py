"""S1: strict AXIS transport, axis_tools callers, Settings identity test, tri state.

Fully offline: an autouse fixture makes any real socket connect raise, and the
transport's HTTP entry point (core.sapphire.axis_http.requests.request) is
mocked. Response shapes follow the AXIS v1 contract (ok/version/data envelope;
401/503 bodies without ok/version).
"""

import json
import logging
import math
import socket

import pytest
import requests

from core.sapphire import axis_http

AXIS_BASE = "https://leak-host.example"
BODY_MARKER = "SECRET-BODY-MARKER"
EXC_MARKER = "SECRET-EXC-MARKER"
OPERATOR = "op-secret-1"
SESSION_ID = "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1"

ACCEPTED_FIELDS = {"trigger", "classification", "next_action", "outcome", "stability", "reference", "impact"}
TAXONOMY = {"narrative", "emotional", "behavioral", "perceptual", "continuity"}
OUTCOMES = {"reduced", "unresolved", "escalated"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


@pytest.fixture(autouse=True)
def axis_env(monkeypatch):
    monkeypatch.setenv("AXIS_BASE_URL", AXIS_BASE)


class FakeResponse:
    def __init__(self, status_code, body=None, text=None):
        self.status_code = status_code
        self._body = body
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")

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
def axis_tools_allowed(monkeypatch):
    from plugins.axis_integration import axis_tools

    monkeypatch.setattr(axis_tools, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))
    return axis_tools


def envelope(data):
    return {"ok": True, "version": "v1", "data": data}


def error_envelope(error):
    return {"ok": False, "version": "v1", "error": error}


def execute_success_body():
    return envelope({"ok": True, "sessionId": SESSION_ID, "outcome": "reduced", "protocol_output": "done"})


def html(status=200):
    return FakeResponse(status, text=f"<html><body>Vercel SSO login {BODY_MARKER}</body></html>")


def assert_no_leak(*values, caplog=None):
    texts = [json.dumps(v, default=str) if not isinstance(v, str) else v for v in values]
    if caplog is not None:
        texts.append(caplog.text)
    for text in texts:
        for secret in (BODY_MARKER, EXC_MARKER, "leak-host", OPERATOR, "x-operator-id"):
            assert secret not in text


# ---- transport ----

@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirects_are_not_followed_and_fail(http, status):
    fake = http(response=FakeResponse(status, text=BODY_MARKER))
    result = axis_http.request_axis("POST", "/api/v2/execute", headers={}, json_body={"trigger": "t"})
    assert result.kind == "redirect" and result.status == status and not result.ok
    assert len(fake.calls) == 1
    assert fake.calls[0]["allow_redirects"] is False


def test_vercel_sso_chain_never_yields_success(http):
    def vercel(method, url, **kwargs):
        # Following the redirect would land on a 200 HTML login page.
        return html(200) if kwargs.get("allow_redirects", True) else FakeResponse(302, text="")

    fake = http(handler=vercel)
    result = axis_http.request_axis("POST", "/api/v2/execute", headers={}, json_body={"trigger": "t"})
    assert result.kind == "redirect" and result.status == 302 and result.data is None
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "response, kind",
    [
        (html(200), "non_json"),
        (FakeResponse(200, text='{"ok": true, "data": '), "non_json"),
        (FakeResponse(200, body=[{"ok": True}]), "non_json"),
        (FakeResponse(200, body={"version": "v1", "data": {}}), "not_ok"),
        (FakeResponse(200, body={"ok": False, "version": "v1", "error": BODY_MARKER}), "not_ok"),
        (FakeResponse(200, body={"ok": "true", "data": {}}), "not_ok"),
        (FakeResponse(200, body={"ok": True, "version": "v1"}), "not_ok"),
        (FakeResponse(200, body={"ok": True, "data": [1, 2]}), "not_ok"),
        (FakeResponse(201, body={"ok": True, "data": None}), "not_ok"),
    ],
    ids=["html", "malformed-json", "json-array", "ok-missing", "ok-false", "ok-string", "data-missing",
         "data-array", "data-null"],
)
def test_2xx_without_valid_envelope_is_not_success(http, response, kind):
    fake = http(response=response)
    result = axis_http.request_axis("GET", "/api/v2/analytics", headers={})
    assert result.kind == kind and not result.ok and result.data is None
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "status, body",
    [
        (401, {"error": "unauthorized"}),
        (503, {"error": "service_unavailable"}),
        (400, error_envelope("guard_blocked")),
        (400, error_envelope("invalid field")),
        (403, error_envelope("forbidden")),
        (405, error_envelope("method not allowed")),
        (429, error_envelope("rate limited")),
        (500, error_envelope("internal_error")),
    ],
)
def test_error_statuses_are_http_error_with_status(http, status, body):
    fake = http(response=FakeResponse(status, body=body))
    result = axis_http.request_axis("POST", "/api/v2/execute", headers={}, json_body={"trigger": "t"})
    assert result.kind == "http_error" and result.status == status and result.data is None
    assert len(fake.calls) == 1


def test_timeout_and_connection_error(http):
    fake = http(exc=requests.Timeout(EXC_MARKER))
    assert axis_http.request_axis("GET", "/api/v2/analytics", headers={}).kind == "timeout"
    assert len(fake.calls) == 1
    fake = http(exc=requests.ConnectionError(EXC_MARKER))
    result = axis_http.request_axis("GET", "/api/v2/analytics", headers={})
    assert result.kind == "connection_error" and result.status is None
    assert len(fake.calls) == 1


def test_missing_base_url_makes_zero_requests(http, monkeypatch):
    monkeypatch.delenv("AXIS_BASE_URL", raising=False)
    fake = http(response=FakeResponse(200, body=envelope({})))
    result = axis_http.request_axis("GET", "/api/v2/analytics", headers={})
    assert result.kind == "not_configured" and result.reason == "missing"
    assert fake.calls == []


def test_success_returns_only_validated_data(http):
    fake = http(response=FakeResponse(200, body=envelope({"total": 3})))
    result = axis_http.request_axis("GET", "/api/v2/analytics", headers={"x-operator-id": OPERATOR})
    assert result.ok and result.kind == "success" and result.status == 200
    assert result.data == {"total": 3}
    call = fake.calls[0]
    assert (call["method"], call["url"]) == ("GET", AXIS_BASE + "/api/v2/analytics")
    assert call["allow_redirects"] is False and call["timeout"] == 20


# ---- axis_tools execute + GET helpers ----

def _execute(axis_tools):
    return axis_tools._execute_axis(
        trigger="des_decision_friction",
        operator_id=OPERATOR,
        classification="perceptual",
        next_action="Review one step.",
        reference=True,
        stability=6,
        impact=4,
    )


def test_execute_verified_success_returns_validated_data(http, axis_tools_allowed):
    fake = http(response=FakeResponse(200, body=execute_success_body()))
    data, ok = _execute(axis_tools_allowed)
    assert ok is True
    assert data["sessionId"] == SESSION_ID
    assert fake.calls[0]["method"] == "POST" and fake.calls[0]["url"].endswith("/api/v2/execute")
    assert fake.calls[0]["headers"] == {"x-operator-id": OPERATOR, "Content-Type": "application/json"}


@pytest.mark.parametrize(
    "data",
    [{"ok": True, "outcome": "reduced"}, {"ok": True, "sessionId": ""}, {"ok": True, "sessionId": "   "},
     {"ok": True, "sessionId": None}, {"ok": True, "sessionId": 42}],
    ids=["missing", "empty", "blank", "null", "number"],
)
def test_execute_envelope_without_session_id_is_not_executed(http, axis_tools_allowed, data):
    http(response=FakeResponse(200, body=envelope(data)))
    result, ok = _execute(axis_tools_allowed)
    assert ok is False
    assert result == {"endpoint": "execute", "status_code": 200, "error": "missing_session_id"}


@pytest.mark.parametrize(
    "status, body", [(401, {"error": "unauthorized"}), (503, {"error": "service_unavailable"}),
                     (400, error_envelope("guard_blocked"))]
)
def test_execute_http_errors_return_kind_and_status_only(http, axis_tools_allowed, status, body, caplog):
    fake = http(response=FakeResponse(status, body=body))
    with caplog.at_level(logging.DEBUG):
        result, ok = _execute(axis_tools_allowed)
    assert ok is False
    assert result == {"endpoint": "execute", "status_code": status, "error": "http_error"}
    assert len(fake.calls) == 1
    assert_no_leak(result, caplog=caplog)


def test_get_helper_success_and_failure_shapes(http, axis_tools_allowed, caplog):
    http(response=FakeResponse(200, body=envelope({"sessions": 2})))
    data, ok = axis_tools_allowed._fetch_axis_analytics(OPERATOR)
    assert ok is True and data == {"sessions": 2}

    http(response=html(200))
    with caplog.at_level(logging.DEBUG):
        result, ok = axis_tools_allowed._fetch_axis_analytics(OPERATOR)
    assert ok is False
    assert result == {"endpoint": "analytics", "status_code": 200, "error": "non_json"}
    assert_no_leak(result, caplog=caplog)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"response": FakeResponse(302, text=BODY_MARKER)},
        {"response": html(200)},
        {"response": FakeResponse(500, body=error_envelope(BODY_MARKER))},
        {"exc": requests.Timeout(EXC_MARKER + " " + AXIS_BASE)},
        {"exc": requests.ConnectionError(EXC_MARKER + " " + AXIS_BASE)},
    ],
    ids=["redirect", "html", "500", "timeout", "connection"],
)
def test_failures_never_leak_body_url_headers_or_exception_text(http, axis_tools_allowed, kwargs, caplog):
    http(**kwargs)
    with caplog.at_level(logging.DEBUG):
        exec_result, _ = _execute(axis_tools_allowed)
        get_result, _ = axis_tools_allowed._fetch_axis_operator_profile(OPERATOR)
    assert set(exec_result) <= {"endpoint", "status_code", "error"}
    assert set(get_result) <= {"endpoint", "status_code", "error"}
    assert_no_leak(exec_result, get_result, caplog=caplog)


# ---- Settings -> Test AXIS Identity ----

@pytest.fixture
def identity_client(monkeypatch, axis_tools_allowed):
    from fastapi.testclient import TestClient

    from core.api_fastapi import app
    from core.auth import require_login
    from core.sapphire import axis_execution_guard
    from core.settings_manager import settings

    monkeypatch.delenv("SAPPHIRE_OPERATOR_ID", raising=False)
    monkeypatch.setattr(axis_execution_guard, "assert_axis_execution_allowed", lambda *a, **k: (True, {}))
    app.dependency_overrides[require_login] = lambda: None
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", OPERATOR, persist=False)
    yield TestClient(app)
    settings.set("OPERATOR_ID", original, persist=False)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"response": FakeResponse(200, body=envelope({"operatorId": "x"}))}, "success"),
        ({"response": FakeResponse(302, text=BODY_MARKER)}, "rejected"),
        ({"response": html(200)}, "rejected"),
        ({"response": FakeResponse(200, body=error_envelope(BODY_MARKER))}, "rejected"),
        ({"response": FakeResponse(401, body={"error": "unauthorized"})}, "rejected"),
        ({"response": FakeResponse(503, body={"error": "service_unavailable"})}, "rejected"),
        ({"exc": requests.Timeout(EXC_MARKER)}, "offline"),
        ({"exc": requests.ConnectionError(EXC_MARKER)}, "offline"),
    ],
    ids=["success", "redirect", "html", "ok-false", "401", "503", "timeout", "connection"],
)
def test_settings_identity_success_only_on_transport_success(http, identity_client, kwargs, expected, caplog):
    fake = http(**kwargs)
    with caplog.at_level(logging.DEBUG):
        response = identity_client.post("/api/settings/operator-id/test-axis-identity")
    assert response.status_code == 200
    assert response.json() == {"status": expected}
    assert len(fake.calls) == 1
    assert fake.calls[0]["method"] == "GET" and fake.calls[0]["url"].endswith("/api/v2/operator-profile")
    assert_no_leak(response.text, caplog=caplog)


# ---- TriSystemFlow success state ----

class _FakeDES:
    def trigger(self, payload):
        return {"show": True}

    def start(self, payload):
        return {"interaction_id": "i-1", "question": {"id": "q1", "text": "Choose one.", "options": ["a"]}}

    def __init__(self, friction_type="information_gap", output_type="clarify"):
        self.result = {"done": True, "friction_type": friction_type, "output": {"output_type": output_type}}

    def answer(self, payload):
        return self.result


def _flow(des=None, **kwargs):
    from core.des.tri_system_flow import TriSystemFlow

    flow = TriSystemFlow(
        des_flow=des or _FakeDES(),
        health_check=lambda: {"ok": True},
        identity_resolver=lambda prompt=False: OPERATOR,
        **kwargs,
    )
    flow.start()
    assert flow.submit_answer("a")["type"] == "result"
    return flow


def _steps(flow):
    return [event["step"] for event in flow.get_trace()]


def test_tri_verified_success_sets_succeeded_and_emits_executed(http, axis_tools_allowed):
    fake = http(response=FakeResponse(200, body=execute_success_body()))
    flow = _flow()
    state = flow.confirm()
    assert state["type"] == "axis_result"
    assert state["data"]["sessionId"] == SESSION_ID
    assert flow.axis_attempted is True and flow.axis_succeeded is True
    assert _steps(flow)[-1] == "AXIS_EXECUTED"
    assert len(fake.calls) == 1

    from ui.views import render_tri_state

    assert f"Reference: {SESSION_ID}" in render_tri_state(state)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"handler": lambda m, u, **k: html(200) if k.get("allow_redirects", True) else FakeResponse(302)},
        {"response": FakeResponse(200, body=envelope({"ok": True}))},
        {"response": FakeResponse(200, body=envelope({"sessionId": ""}))},
        {"response": FakeResponse(401, body={"error": "unauthorized"})},
        {"response": FakeResponse(400, body=error_envelope("guard_blocked"))},
        {"exc": requests.Timeout(EXC_MARKER)},
    ],
    ids=["sso-redirect", "no-session-id", "empty-session-id", "401", "guard-blocked", "timeout"],
)
def test_tri_failure_is_not_executed_and_never_redispatches(http, axis_tools_allowed, kwargs):
    fake = http(**kwargs)
    flow = _flow()
    first = flow.confirm()
    second = flow.confirm()

    assert first["type"] == "error"
    assert set(first["data"]["detail"]) == {"error", "status_code"}
    assert flow.axis_attempted is True and flow.axis_succeeded is False
    assert "AXIS_EXECUTED" not in _steps(flow)
    assert _steps(flow)[-1] == "AXIS_REJECTED"
    assert second["type"] == "error"
    assert len(fake.calls) == 1
    assert_no_leak(first, second)


def test_tri_rejects_executor_success_without_session_id(http):
    flow = _flow(axis_executor=lambda **kwargs: ({"ok": True}, True))
    state = flow.confirm()
    assert state["type"] == "error"
    assert state["data"]["detail"] == {"error": "missing_session_id", "status_code": None}
    assert flow.axis_succeeded is False
    assert "AXIS_EXECUTED" not in _steps(flow)


def test_tri_reject_makes_zero_axis_requests(http, axis_tools_allowed):
    fake = http(response=FakeResponse(200, body=execute_success_body()))
    flow = _flow()
    flow.axis_preview()
    assert flow.cancel() == {"type": "idle", "data": {}}
    assert fake.calls == []
    assert flow.axis_attempted is False and flow.axis_succeeded is False


def test_web_bridge_reject_makes_zero_axis_requests(http, axis_tools_allowed):
    from core.des.tri_system_flow import TriSystemFlow
    from core.des.web_tri_system import WebTriSystemBridge

    fake = http(response=FakeResponse(200, body=execute_success_body()))
    bridge = WebTriSystemBridge(
        flow_factory=lambda: TriSystemFlow(
            des_flow=_FakeDES(), health_check=lambda: {"ok": True},
            identity_resolver=lambda prompt=False: OPERATOR,
        )
    )
    bridge.handle("tri")
    bridge.handle("a")
    bridge.handle("reject")
    assert fake.calls == []


# ---- outgoing tri execute payload satisfies the AXIS contract ----

def _des_cases():
    from core.des.axis_preview import FRICTION_TO_CLASSIFICATION, OUTPUT_TO_NEXT_ACTION

    frictions = list(FRICTION_TO_CLASSIFICATION) + ["not-a-known-friction"]
    outputs = list(OUTPUT_TO_NEXT_ACTION) + ["not-a-known-output"]
    return [(f, o) for f in frictions for o in outputs]


@pytest.mark.parametrize("friction_type, output_type", _des_cases())
def test_tri_execute_payload_satisfies_axis_contract(http, axis_tools_allowed, friction_type, output_type):
    fake = http(response=FakeResponse(200, body=execute_success_body()))
    flow = _flow(des=_FakeDES(friction_type, output_type))
    assert flow.confirm()["type"] == "axis_result"

    body = fake.calls[0]["json"]
    assert set(body) <= ACCEPTED_FIELDS
    assert "fracture_id" not in body
    for field in ("trigger", "classification", "next_action"):
        assert isinstance(body[field], str) and body[field].strip()
    assert body["classification"] in TAXONOMY
    assert all(value is not None for value in body.values())
    assert body.get("reference") is True
    for field, low, high in (("stability", 0, 10), ("impact", 0, 10)):
        value = body[field]
        assert isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        assert low <= value <= high
    assert body["stability"] >= 3
    assert body["impact"] <= 7
    assert body.get("outcome", "reduced") in OUTCOMES


def test_every_classification_map_entry_is_in_axis_taxonomy():
    from core.des.axis_preview import FRICTION_TO_CLASSIFICATION

    assert set(FRICTION_TO_CLASSIFICATION.values()) <= TAXONOMY


# ---- untrusted executor output is never forwarded ----

def test_tri_failure_detail_drops_malicious_executor_output():
    malicious_error = f"https://user:pw@{BODY_MARKER}.example/leak?token={EXC_MARKER}"
    flow = _flow(
        axis_executor=lambda **kwargs: (
            {
                "error": malicious_error,
                "status_code": f"500 {AXIS_BASE}",
                "reason": BODY_MARKER,
                "message": EXC_MARKER,
                "endpoint": AXIS_BASE,
                "token": "Bearer " + BODY_MARKER,
                "response_text": BODY_MARKER,
            },
            False,
        )
    )
    state = flow.confirm()

    assert state["type"] == "error"
    assert state["data"]["message"] == "AXIS execution failed."
    assert state["data"]["detail"] == {"error": "axis_failed", "status_code": None}
    assert flow.axis_succeeded is False
    assert "AXIS_EXECUTED" not in _steps(flow)
    for text in (json.dumps(state, default=str), json.dumps(flow.get_trace(), default=str),
                 json.dumps(flow.get_gate_events(), default=str)):
        for secret in (BODY_MARKER, EXC_MARKER, "leak-host", "user:pw", "Bearer"):
            assert secret not in text


@pytest.mark.parametrize(
    "status, expected",
    [(503, 503), (100, 100), (599, 599), (True, None), (False, None), (99, None), (600, None),
     (503.0, None), ("503", None), (None, None), ([503], None)],
)
def test_tri_failure_detail_keeps_only_valid_http_status(status, expected):
    flow = _flow(axis_executor=lambda **kwargs: ({"error": "http_error", "status_code": status}, False))
    state = flow.confirm()
    assert state["data"]["detail"] == {"error": "http_error", "status_code": expected}
    assert flow.axis_succeeded is False


def test_tri_failure_detail_keeps_allowed_kind_and_drops_extra_fields():
    flow = _flow(
        axis_executor=lambda **kwargs: (
            {"endpoint": "execute", "error": "http_error", "status_code": 401, "response_text": BODY_MARKER},
            False,
        )
    )
    state = flow.confirm()
    assert state["data"]["detail"] == {"error": "http_error", "status_code": 401}
    assert BODY_MARKER not in json.dumps(state)


def test_tri_not_configured_kind_keeps_fixed_message_without_extra_fields():
    flow = _flow(
        axis_executor=lambda **kwargs: (
            {"error": "axis_not_configured", "status_code": None, "reason": BODY_MARKER, "message": EXC_MARKER},
            False,
        )
    )
    state = flow.confirm()
    assert state["data"]["message"] == "AXIS is not configured. Execution stopped."
    assert state["data"]["detail"] == {"error": "axis_not_configured", "status_code": None}
    assert BODY_MARKER not in json.dumps(state) and EXC_MARKER not in json.dumps(state)
