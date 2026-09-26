"""S4: tri bridge isolation (signed-session principal + server-minted tab token).

Fully offline: tests/offline_guard.py's no_network fixture blocks every real
socket connect, DES is a fake, and the AXIS executor is a recorder. The AXIS
transport entry point (core.sapphire.axis_http.requests.request) is also
replaced with a recorder so any real AXIS dispatch would be counted.

Browser sessions are real signed Starlette session cookies (signed with the
app's own SessionMiddleware secret), so the CSRF middleware and require_login
run exactly as in production.
"""

import importlib.util
import json
import logging
import sys
import threading
import time
from base64 import b64decode, b64encode
from pathlib import Path

import itsdangerous
import pytest
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from core import api_fastapi, auth
from core.des import web_tri_system
from core.des.tri_system_flow import TriSystemFlow
from core.des.web_tri_system import (
    MAX_TRI_TABS,
    TRI_API_KEY_DENIED_MESSAGE,
    TRI_TAB_INVALID_MESSAGE,
    TRI_TAB_TOKEN_HEADER,
    TriBridgeRegistry,
)
from core.sapphire import axis_http
from core.security import violations

chat_routes = sys.modules["core.routes.chat"]
ROOT = Path(__file__).resolve().parents[1]

_GUARD_PATH = Path(__file__).with_name("offline_guard.py")
_spec = importlib.util.spec_from_file_location("s4_offline_guard", _GUARD_PATH)
_offline_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_offline_guard)

# Registers the autouse fixture for every test in this module.
no_network = _offline_guard.no_network

OPERATOR = "op-S4-OPERATOR-MARKER"
API_KEY = "S4-API-KEY-MARKER"
CSRF_A = "s4-csrf-session-a"
CSRF_B = "s4-csrf-session-b"
SESSION_COOKIE = "sapphire_session"
SESSION_ID = "0b7f3c1e-8a55-4d0b-9a44-3c0f5ad2e6a1"

TRI_START = "tri"
DES_ANSWER = "a"


# ---- fakes ----

class FakeDES:
    def trigger(self, payload):
        return {"show": True}

    def start(self, payload):
        return {"interaction_id": "i-1", "question": {"id": "q1", "text": "Choose one.", "options": ["a"]}}

    def answer(self, payload):
        return {"done": True, "friction_type": "information_gap", "output": {"output_type": "clarify"}}


class AxisRecorder:
    def __init__(self, delay=0.0):
        self.calls = []
        self.delay = delay
        self._lock = threading.Lock()

    def __call__(self, **kwargs):
        if self.delay:
            time.sleep(self.delay)
        with self._lock:
            self.calls.append(kwargs)
        return {"ok": True, "sessionId": SESSION_ID}, True


class FakeSystem:
    def __init__(self):
        self.llm_calls = []

    def web_active_inc(self):
        pass

    def web_active_dec(self):
        pass

    def process_llm_query(self, text, skip_tts=False):
        self.llm_calls.append(text)
        return "normal chat reply"


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


# ---- fixtures ----

@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    for name in ("AXIS_BASE_URL", "AXIS_SERVICE_TOKEN", "VERCEL_PROTECTION_BYPASS_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(violations, "VIOLATION_LOG_PATH", tmp_path / "logs" / "violations.log")
    auth._endpoint_limits.clear()
    yield
    auth._endpoint_limits.clear()


@pytest.fixture
def axis_transport(monkeypatch):
    calls = []

    def record(*args, **kwargs):
        calls.append(args)
        raise AssertionError("AXIS transport reached")

    monkeypatch.setattr(axis_http.requests, "request", record)
    return calls


@pytest.fixture
def axis():
    return AxisRecorder()


def make_registry(axis_recorder, **kwargs):
    def flow_factory():
        return TriSystemFlow(
            des_flow=FakeDES(),
            health_check=lambda: {"ok": True},
            identity_resolver=lambda prompt=False: OPERATOR,
            axis_executor=axis_recorder,
        )

    return TriBridgeRegistry(flow_factory=flow_factory, **kwargs)


@pytest.fixture
def registry(monkeypatch, axis):
    reg = make_registry(axis)
    monkeypatch.setattr(chat_routes, "get_web_tri_registry", lambda: reg)
    return reg


@pytest.fixture
def system():
    fake = FakeSystem()
    api_fastapi.app.dependency_overrides[api_fastapi.get_system] = lambda: fake
    try:
        yield fake
    finally:
        api_fastapi.app.dependency_overrides.pop(api_fastapi.get_system, None)


@pytest.fixture(autouse=True)
def setup_complete(monkeypatch):
    import core.setup as setup

    monkeypatch.setattr(setup, "is_setup_complete", lambda: True)
    monkeypatch.setattr(setup, "get_password_hash", lambda: API_KEY)


def _session_secret():
    for middleware in api_fastapi.app.user_middleware:
        if middleware.cls is SessionMiddleware:
            return middleware.kwargs["secret_key"]
    raise AssertionError("SessionMiddleware not installed")


def _signed_session(data):
    signer = itsdangerous.TimestampSigner(str(_session_secret()))
    return signer.sign(b64encode(json.dumps(data).encode("utf-8"))).decode("utf-8")


# The session cookie is Secure when WEB_UI_SSL_ADHOC is on (the default), so
# clients talk https to the in-process app (no network is involved).
BASE_URL = "https://testserver"
COOKIE_DOMAIN = "testserver.local"  # where the TestClient jar stores the server's cookie


def set_session(client, data):
    client.cookies.set(SESSION_COOKIE, _signed_session(data), domain=COOKIE_DOMAIN, path="/")


def _read_session(client):
    raw = client.cookies.get(SESSION_COOKIE)
    if raw is None:  # cookie cleared (e.g. logout)
        return {}
    signer = itsdangerous.TimestampSigner(str(_session_secret()))
    return json.loads(b64decode(signer.unsign(raw.encode("utf-8"))))


class Browser:
    """One signed-in browser (own cookie jar); tabs are distinguished by token."""

    def __init__(self, csrf):
        self.csrf = csrf
        self.client = TestClient(api_fastapi.app, base_url=BASE_URL)
        set_session(self.client, {"logged_in": True, "username": "user", "csrf_token": csrf})

    def tab_token(self, csrf=True):
        headers = {"X-CSRF-Token": self.csrf} if csrf else {}
        return self.client.post("/api/tri/tab-token", headers=headers)

    def new_tab(self):
        response = self.tab_token()
        assert response.status_code == 200
        return response.json()["token"]

    def chat(self, text, token=None, stream=False, csrf=True):
        headers = {"X-CSRF-Token": self.csrf} if csrf else {}
        if token is not None:
            headers[TRI_TAB_TOKEN_HEADER] = token
        path = "/api/chat/stream" if stream else "/api/chat"
        return self.client.post(path, json={"text": text}, headers=headers)

    def principal(self):
        return _read_session(self.client).get("tri_principal")

    def cookie(self):
        return self.client.cookies.get(SESSION_COOKIE)


def reply(response):
    assert response.status_code == 200
    return response.json()["response"]


def sse_text(response):
    assert response.status_code == 200
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    return "".join(e.get("text", "") for e in events if e.get("type") == "content"), events


def reach_confirmation(browser, token):
    assert "A few questions" in reply(browser.chat(TRI_START, token))
    text = reply(browser.chat(DES_ANSWER, token))
    assert "Type confirm to execute AXIS." in text


# ---- CSRF finding (step 1) ----

def test_csrf_streaming_chat_without_token_is_rejected(registry, system):
    browser = Browser(CSRF_A)
    for path in ("/api/chat/stream", "/api/chat"):
        response = browser.client.post(path, json={"text": "hello"})
        assert response.status_code == 403
        assert response.json() == {"detail": "CSRF validation failed"}
    assert system.llm_calls == []


def test_csrf_streaming_chat_with_session_token_passes(registry, system):
    browser = Browser(CSRF_A)
    assert browser.chat("hello", csrf=True).status_code == 200
    text, events = sse_text(browser.chat(TRI_START, token=browser.new_tab(), stream=True))
    assert "A few questions" in text
    assert events[-1] == {"done": True, "hybrid": True}


def test_csrf_client_supplies_token_via_global_fetch_wrapper():
    """The stream sends use bare fetch(); index.html's wrapper adds X-CSRF-Token for /api/ URLs."""
    index = (ROOT / "interfaces/web/templates/index.html").read_text(encoding="utf-8")
    api_js = (ROOT / "interfaces/web/static/api.js").read_text(encoding="utf-8")
    assert "window.fetch = function(url, opts)" in index
    assert "url.startsWith('/api/')" in index
    assert "'X-CSRF-Token': csrf" in index
    assert api_js.count("await fetch('/api/chat/stream'") == 2


# ---- token endpoint ----

def test_token_endpoint_requires_login(registry):
    client = TestClient(api_fastapi.app, base_url=BASE_URL)
    response = client.post("/api/tri/tab-token")
    assert response.status_code == 401
    assert len(registry) == 0


def test_token_endpoint_requires_csrf(registry):
    browser = Browser(CSRF_A)
    response = browser.tab_token(csrf=False)
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}
    response = browser.client.post("/api/tri/tab-token", headers={"X-CSRF-Token": CSRF_B})
    assert response.status_code == 403
    assert len(registry) == 0


def test_token_endpoint_denies_api_key_callers(registry):
    client = TestClient(api_fastapi.app, base_url=BASE_URL)
    response = client.post("/api/tri/tab-token", headers={"X-API-Key": API_KEY})
    assert response.status_code == 403
    assert response.json() == {"detail": chat_routes.TRI_TAB_TOKEN_DENIED_DETAIL}
    # A browser session that also presents an API key is treated as an API-key caller.
    browser = Browser(CSRF_A)
    response = browser.client.post("/api/tri/tab-token", headers={"X-API-Key": API_KEY})
    assert response.status_code == 403
    assert len(registry) == 0
    assert API_KEY not in response.text


def test_token_endpoint_returns_distinct_tokens_bound_to_random_principal(registry):
    browser = Browser(CSRF_A)
    first, second = browser.new_tab(), browser.new_tab()
    assert first != second
    assert len(first) >= 43 and len(second) >= 43
    principal = browser.principal()
    assert isinstance(principal, str) and len(principal) >= 43
    assert principal not in (CSRF_A, "user", OPERATOR, first, second)
    # Principal is stable for the session; tokens are bound to it.
    browser.new_tab()
    assert browser.principal() == principal
    assert registry._lookup(first, principal) is not None
    assert registry._lookup(first, "other-principal") is None

    other = Browser(CSRF_B)
    other.new_tab()
    assert other.principal() != principal


def test_principal_is_not_taken_from_client_input(registry):
    browser = Browser(CSRF_A)
    response = browser.client.post(
        "/api/tri/tab-token",
        headers={"X-CSRF-Token": CSRF_A, "X-Tri-Principal": "attacker"},
        json={"tri_principal": "attacker"},
    )
    assert response.status_code == 200
    assert browser.principal() != "attacker"


# ---- cross-session isolation ----

def test_cross_session_cannot_confirm_or_use_another_sessions_token(registry, system, axis, axis_transport):
    a, b = Browser(CSRF_A), Browser(CSRF_B)
    token_a = a.new_tab()
    reach_confirmation(a, token_a)

    # B has its own tab: "confirm" never reaches A's flow.
    token_b = b.new_tab()
    assert b.chat("confirm", token_b).json()["response"] == "normal chat reply"
    # B replays A's token: principal mismatch -> no flow, fail closed on start.
    assert reply(b.chat("confirm", token_a)) == "normal chat reply"
    assert reply(b.chat("reject", token_a)) == "normal chat reply"
    response = b.chat(TRI_START, token_a)
    assert response.json() == {"response": TRI_TAB_INVALID_MESSAGE, "tri_token_invalid": True}
    assert axis.calls == [] and axis_transport == []

    # A's flow is untouched and still executes exactly once.
    assert "Action Result" in reply(a.chat("confirm", token_a))
    assert len(axis.calls) == 1
    assert axis_transport == []


# ---- cross-tab isolation within one session ----

def test_cross_tab_same_session_is_isolated(registry, system, axis):
    browser = Browser(CSRF_A)
    tab1, tab2 = browser.new_tab(), browser.new_tab()
    reach_confirmation(browser, tab1)

    assert reply(browser.chat("confirm", tab2)) == "normal chat reply"
    assert reply(browser.chat("reject", tab2)) == "normal chat reply"
    assert axis.calls == []

    # Tab 2 running its own flow does not disturb tab 1.
    assert "A few questions" in reply(browser.chat(TRI_START, tab2))
    assert "Type confirm to execute AXIS." in reply(browser.chat(DES_ANSWER, tab2))
    assert "Review Action\nIdle" in reply(browser.chat("reject", tab2))
    assert registry._entries[tab1].bridge.flow.pending_execution is not None

    assert "Action Result" in reply(browser.chat("confirm", tab1))
    assert len(axis.calls) == 1


def test_stream_route_uses_the_same_tab_isolation(registry, system, axis):
    browser = Browser(CSRF_A)
    tab1, tab2 = browser.new_tab(), browser.new_tab()
    text, _ = sse_text(browser.chat(TRI_START, tab1, stream=True))
    assert "A few questions" in text
    text, _ = sse_text(browser.chat(DES_ANSWER, tab1, stream=True))
    assert "Type confirm to execute AXIS." in text
    text, events = sse_text(browser.chat(TRI_START, None, stream=True))
    assert text == TRI_TAB_INVALID_MESSAGE
    assert events[-1] == {"done": True, "hybrid": True, "tri_token_invalid": True}
    text, _ = sse_text(browser.chat("confirm", tab1, stream=True))
    assert "Action Result" in text
    assert len(axis.calls) == 1


# ---- concurrency ----

def test_concurrent_double_confirm_dispatches_at_most_once(monkeypatch):
    axis = AxisRecorder(delay=0.2)
    reg = make_registry(axis)
    principal = "p" * 43
    token = reg.issue_token(principal)
    route = dict(tab_token=token, principal=principal, browser_session=True)
    reg.handle(TRI_START, **route)
    assert "Type confirm" in reg.handle(DES_ANSWER, **route).text

    barrier = threading.Barrier(8)
    results = []

    def confirm():
        barrier.wait()
        results.append(reg.handle("confirm", **route).text)

    threads = [threading.Thread(target=confirm) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(axis.calls) == 1
    assert sum(1 for r in results if r and "Action Result" in r) == 1


def test_concurrent_confirm_over_http_dispatches_at_most_once(registry, system, axis):
    axis.delay = 0.1
    browser = Browser(CSRF_A)
    token = browser.new_tab()
    reach_confirmation(browser, token)
    barrier = threading.Barrier(4)
    statuses = []

    def confirm():
        barrier.wait()
        statuses.append(browser.chat("confirm", token).status_code)

    threads = [threading.Thread(target=confirm) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert statuses == [200] * 4
    assert len(axis.calls) == 1


# ---- missing / unknown / expired tokens ----

@pytest.mark.parametrize("token", [None, "", "unknown-token-value"], ids=["missing", "empty", "unknown"])
def test_invalid_token_fails_closed_and_normal_chat_unaffected(registry, system, axis, axis_transport, token):
    browser = Browser(CSRF_A)
    browser.new_tab()
    response = browser.chat(TRI_START, token)
    assert response.json() == {"response": TRI_TAB_INVALID_MESSAGE, "tri_token_invalid": True}
    for command in ("confirm", "reject", "cancel", DES_ANSWER):
        assert reply(browser.chat(command, token)) == "normal chat reply"
    assert reply(browser.chat("hello there", token)) == "normal chat reply"
    assert axis.calls == [] and axis_transport == []
    assert system.llm_calls == ["confirm", "reject", "cancel", DES_ANSWER, "hello there"]


def test_expired_token_fails_closed(system, axis, monkeypatch):
    clock = Clock()
    reg = make_registry(axis, clock=clock)
    monkeypatch.setattr(chat_routes, "get_web_tri_registry", lambda: reg)
    browser = Browser(CSRF_A)
    token = browser.new_tab()
    clock.now += web_tri_system.TRI_TAB_IDLE_SECONDS + 1
    assert browser.chat(TRI_START, token).json()["tri_token_invalid"] is True
    assert len(reg) == 0
    assert axis.calls == []


def test_expired_pending_is_not_executed_after_idle_expiry(system, axis, monkeypatch):
    clock = Clock()
    reg = make_registry(axis, clock=clock)
    monkeypatch.setattr(chat_routes, "get_web_tri_registry", lambda: reg)
    browser = Browser(CSRF_A)
    token = browser.new_tab()
    reach_confirmation(browser, token)
    # The flow's pending expiry uses wall time; age it past its TTL too.
    bridge = reg._entries[token].bridge
    bridge.flow.pending_execution["expires_at"] = time.time() - 1
    clock.now += web_tri_system.TRI_TAB_IDLE_SECONDS + 1
    assert reply(browser.chat("confirm", token)) == "normal chat reply"
    assert axis.calls == []


def test_logout_clears_principal_and_orphans_tokens(registry, system, axis):
    browser = Browser(CSRF_A)
    token = browser.new_tab()
    reach_confirmation(browser, token)
    assert browser.client.post("/logout", headers={"X-CSRF-Token": CSRF_A}).status_code == 200
    assert "tri_principal" not in _read_session(browser.client)
    # Log back in (same browser, new session contents): old token no longer matches.
    set_session(browser.client, {"logged_in": True, "username": "user", "csrf_token": CSRF_A})
    assert reply(browser.chat("confirm", token)) == "normal chat reply"
    assert axis.calls == []


# ---- API-key callers ----

def test_api_key_caller_is_denied_tri(registry, system, axis):
    browser = Browser(CSRF_A)
    token = browser.new_tab()
    reach_confirmation(browser, token)

    api = TestClient(api_fastapi.app, base_url=BASE_URL)
    response = api.post("/api/chat", json={"text": TRI_START}, headers={"X-API-Key": API_KEY})
    assert response.json() == {"response": TRI_API_KEY_DENIED_MESSAGE}
    headers = {"X-API-Key": API_KEY, TRI_TAB_TOKEN_HEADER: token}
    assert reply(api.post("/api/chat", json={"text": "confirm"}, headers=headers)) == "normal chat reply"
    # Browser cookie + API key header: CSRF is skipped for it, so tri is denied too.
    response = browser.client.post("/api/chat", json={"text": "confirm"}, headers=headers)
    assert reply(response) == "normal chat reply"
    assert axis.calls == []
    assert "Action Result" in reply(browser.chat("confirm", token))
    assert len(axis.calls) == 1


# ---- registry bounds ----

def _live_tab(reg, principal):
    token = reg.issue_token(principal)
    route = dict(tab_token=token, principal=principal, browser_session=True)
    reg.handle(TRI_START, **route)
    assert "Type confirm" in reg.handle(DES_ANSWER, **route).text
    return token


def test_registry_cap_is_enforced_by_evicting_lru_idle_entries(axis):
    clock = Clock()
    reg = make_registry(axis, max_tabs=4, clock=clock)
    tokens = []
    for _ in range(4):
        tokens.append(reg.issue_token("p"))
        clock.now += 1
    newest = reg.issue_token("p")
    assert len(reg) == 4
    assert tokens[0] not in reg._entries  # least recently used, no pending
    assert newest in reg._entries


def test_default_cap_constant():
    assert MAX_TRI_TABS == 256
    assert TriBridgeRegistry().max_tabs == MAX_TRI_TABS
    assert web_tri_system.TRI_TAB_IDLE_SECONDS == 30 * 60


def test_live_pending_entries_are_never_evicted(axis):
    clock = Clock()
    reg = make_registry(axis, max_tabs=3, clock=clock)
    live = [_live_tab(reg, "p") for _ in range(2)]
    idle = reg.issue_token("p")
    clock.now += 1
    fresh = reg.issue_token("p")
    assert fresh is not None
    assert idle not in reg._entries
    for token in live:
        assert token in reg._entries


def test_full_of_live_entries_fails_closed_for_new_tabs(registry, system, axis, monkeypatch):
    reg = make_registry(axis, max_tabs=2)
    monkeypatch.setattr(chat_routes, "get_web_tri_registry", lambda: reg)
    browser = Browser(CSRF_A)
    principal_token = browser.new_tab()
    principal = browser.principal()
    reach_confirmation(browser, principal_token)
    _live_tab(reg, principal)

    response = browser.tab_token()
    assert response.status_code == 503
    assert response.json() == {"detail": web_tri_system.TRI_CAPACITY_MESSAGE}
    assert browser.chat(TRI_START, None).json()["response"] == TRI_TAB_INVALID_MESSAGE
    assert axis.calls == []
    assert len(reg) == 2


def test_idle_entries_expire(axis):
    clock = Clock()
    reg = make_registry(axis, clock=clock)
    idle = reg.issue_token("p")
    live = _live_tab(reg, "p")
    clock.now += web_tri_system.TRI_TAB_IDLE_SECONDS + 1
    reg.issue_token("p")  # issuance purges idle entries
    assert idle not in reg._entries
    assert live in reg._entries  # its pending execution (wall-clock TTL) is still live


# ---- leak checks ----

def test_no_token_principal_cookie_or_operator_leaks(registry, system, axis, caplog, tmp_path):
    with caplog.at_level(logging.DEBUG):
        a, b = Browser(CSRF_A), Browser(CSRF_B)
        token_a, token_b = a.new_tab(), b.new_tab()
        outputs = []
        outputs.append(a.chat(TRI_START, token_a).text)
        outputs.append(a.chat(DES_ANSWER, token_a).text)
        outputs.append(b.chat(TRI_START, token_a).text)
        outputs.append(b.chat("confirm", token_a).text)
        outputs.append(a.chat(TRI_START, None, stream=True).text)
        outputs.append(a.chat("confirm", token_a).text)
        outputs.append(TestClient(api_fastapi.app, base_url=BASE_URL).post(
            "/api/chat", json={"text": TRI_START}, headers={"X-API-Key": API_KEY}).text)
        outputs.append(repr(registry._entries[token_a]))

    secrets_ = [token_a, token_b, a.principal(), b.principal(), a.cookie(), b.cookie(), OPERATOR, API_KEY]
    log_path = violations.VIOLATION_LOG_PATH
    blobs = outputs + [caplog.text, log_path.read_text(encoding="utf-8") if log_path.exists() else ""]
    for blob in blobs:
        for secret in secrets_:
            assert secret not in blob
    assert len(axis.calls) == 1


# ---- the process-wide bridge is gone ----

def test_no_process_wide_bridge_remains():
    assert not hasattr(web_tri_system, "get_web_tri_system_bridge")
    assert not hasattr(web_tri_system, "_WEB_TRI_SYSTEM_BRIDGE")
    assert not hasattr(chat_routes, "get_web_tri_system_bridge")
