"""S4.1: session signing secret separated from the password hash, login
issues a fresh session, and only a valid API key skips CSRF.

Fully offline: tests/offline_guard.py's no_network fixture blocks every real
socket connect. Sessions are real signed Starlette cookies. The session secret
lives in a per-run temporary file (root conftest.py); nothing here reads or
writes the real user config directory.
"""

import importlib.util
import json
import os
import subprocess
import sys
import threading
from base64 import b64decode, b64encode
from pathlib import Path

import bcrypt
import itsdangerous
import pytest
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import core.setup as setup
from core import api_fastapi, auth
from core.routes import chat as chat_routes

ROOT = Path(__file__).resolve().parents[1]

_GUARD_PATH = Path(__file__).with_name("offline_guard.py")
_spec = importlib.util.spec_from_file_location("s4_1_offline_guard", _GUARD_PATH)
_offline_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_offline_guard)

# Registers the autouse fixture for every test in this module.
no_network = _offline_guard.no_network

PASSWORD = "s4-1-correct-password"
PASSWORD_HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
API_KEY = "s4-2-internal-api-key-" + "k" * 48
SESSION_COOKIE = "sapphire_session"
BASE_URL = "https://testserver"
COOKIE_DOMAIN = "testserver.local"
PRE_LOGIN_CSRF = "s4-1-pre-login-csrf"
PRE_LOGIN_PRINCIPAL = "s4-1-pre-login-principal"
CSRF = "s4-1-logged-in-csrf"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """Setup complete with a known password hash and a separate API key (S4.2).

    Also removes any require_login dependency override another test module
    installed at import time, so authentication runs for real here.
    """
    monkeypatch.delitem(api_fastapi.app.dependency_overrides, auth.require_login, raising=False)
    for module in (setup, api_fastapi):
        monkeypatch.setattr(module, "is_setup_complete", lambda: True)
        monkeypatch.setattr(module, "get_password_hash", lambda: PASSWORD_HASH)
    monkeypatch.setattr(setup, "get_api_key", lambda: API_KEY)
    auth._rate_limits.clear()
    auth._endpoint_limits.clear()
    yield
    auth._rate_limits.clear()
    auth._endpoint_limits.clear()


def _session_secret():
    for middleware in api_fastapi.app.user_middleware:
        if middleware.cls is SessionMiddleware:
            return middleware.kwargs["secret_key"]
    raise AssertionError("SessionMiddleware not installed")


def _sign(data, key):
    signer = itsdangerous.TimestampSigner(str(key))
    return signer.sign(b64encode(json.dumps(data).encode("utf-8"))).decode("utf-8")


def _client(session=None, key=None):
    client = TestClient(api_fastapi.app, base_url=BASE_URL)
    if session is not None:
        client.cookies.set(SESSION_COOKIE, _sign(session, key or _session_secret()), domain=COOKIE_DOMAIN, path="/")
    return client


def _read_session(client):
    raw = client.cookies.get(SESSION_COOKIE)
    if raw is None:
        return {}
    signer = itsdangerous.TimestampSigner(str(_session_secret()))
    return json.loads(b64decode(signer.unsign(raw.encode("utf-8"))))


def _logged_in(**extra):
    return {"logged_in": True, "username": "user", "csrf_token": CSRF, **extra}


def _login(client, password=PASSWORD, csrf=PRE_LOGIN_CSRF):
    return client.post(
        "/login",
        data={"password": password, "csrf_token": csrf},
        follow_redirects=False,
    )


# ---- 1. dedicated session signing secret ----

def test_session_secret_is_not_the_password_hash_or_api_key():
    secret = _session_secret()
    assert secret != PASSWORD_HASH
    assert not str(secret).startswith("$2")
    assert len(secret) >= 64


def test_session_secret_comes_from_the_injected_test_path():
    path = setup.get_session_secret_path()
    assert path != setup.SESSION_SECRET_FILE
    assert path.read_text(encoding="ascii").strip() == _session_secret()


def test_suite_does_not_touch_the_real_config_secret():
    """conftest recorded the real file's stat before any import; it must be unchanged."""
    before = os.environ["SAPPHIRE_TEST_REAL_SESSION_SECRET_STATE"]
    try:
        stat = setup.SESSION_SECRET_FILE.stat()
        now = f"present:{stat.st_mtime_ns}:{stat.st_size}"
    except FileNotFoundError:
        now = "absent"
    assert now == before


def test_cookie_signed_with_password_hash_is_rejected():
    """Old cookies (signed with the hash) and hash-forged new cookies are not sessions."""
    forged = _client(_logged_in(), key=PASSWORD_HASH)
    response = forged.post("/logout", headers={"X-CSRF-Token": CSRF}, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"

    genuine = _client(_logged_in())
    assert genuine.post("/logout", headers={"X-CSRF-Token": CSRF}).status_code == 200


def test_cookie_signed_with_password_hash_cannot_mint_a_tri_tab_token():
    forged = _client(_logged_in(), key=PASSWORD_HASH)
    response = forged.post("/api/tri/tab-token", headers={"X-CSRF-Token": CSRF})
    assert response.status_code == 401


def test_secret_persists_across_calls_and_restart(tmp_path):
    path = tmp_path / "cfg" / "session_secret"
    first = setup.load_or_create_session_secret(path)
    assert setup.load_or_create_session_secret(path) == first

    # A fresh interpreter (a restart) reads the same secret.
    env = dict(os.environ, SAPPHIRE_SESSION_SECRET_FILE=str(path))
    result = subprocess.run(
        [sys.executable, "-c", "from core.setup import load_or_create_session_secret as f; print(f())"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == first


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_secret_file_is_private_on_posix(tmp_path):
    path = tmp_path / "session_secret"
    setup.load_or_create_session_secret(path)
    assert path.stat().st_mode & 0o077 == 0


def test_concurrent_creation_yields_one_secret(tmp_path):
    path = tmp_path / "session_secret"
    barrier = threading.Barrier(16)
    results, errors = [], []

    def worker():
        barrier.wait()
        try:
            results.append(setup.load_or_create_session_secret(path))
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(set(results)) == 1
    assert results[0] == path.read_text(encoding="ascii").strip()
    assert [p.name for p in tmp_path.iterdir()] == ["session_secret"]  # no temp files left


def test_unpersistable_secret_fails_closed(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    with pytest.raises(setup.SessionSecretError):
        setup.load_or_create_session_secret(blocker / "session_secret")


def test_invalid_existing_secret_fails_closed_and_is_not_overwritten(tmp_path):
    path = tmp_path / "session_secret"
    path.write_text("short")
    with pytest.raises(setup.SessionSecretError):
        setup.load_or_create_session_secret(path)
    assert path.read_text() == "short"


def test_app_import_fails_closed_when_secret_cannot_be_persisted(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    env = dict(os.environ, SAPPHIRE_SESSION_SECRET_FILE=str(blocker / "session_secret"))
    result = subprocess.run(
        [sys.executable, "-c", "import core.api_fastapi"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "SessionSecretError" in result.stderr


# ---- 2. login issues a fresh session ----

def test_login_clears_pre_login_session_and_rotates_csrf():
    client = _client({"csrf_token": PRE_LOGIN_CSRF, "tri_principal": PRE_LOGIN_PRINCIPAL, "stale": "x"})
    response = _login(client)
    assert response.status_code == 302
    assert response.headers["location"] == "/"

    session = _read_session(client)
    assert set(session) == {"logged_in", "username", "csrf_token"}
    assert session["logged_in"] is True
    assert session["csrf_token"] != PRE_LOGIN_CSRF
    assert len(session["csrf_token"]) == 64
    assert "tri_principal" not in session


def test_pre_login_csrf_token_is_useless_after_login():
    client = _client({"csrf_token": PRE_LOGIN_CSRF})
    _login(client)
    assert client.post("/logout", headers={"X-CSRF-Token": PRE_LOGIN_CSRF}).status_code == 403
    new_csrf = _read_session(client)["csrf_token"]
    assert client.post("/logout", headers={"X-CSRF-Token": new_csrf}).status_code == 200


def test_tri_principal_is_minted_fresh_after_login():
    client = _client({"csrf_token": PRE_LOGIN_CSRF, "tri_principal": PRE_LOGIN_PRINCIPAL})
    _login(client)
    csrf = _read_session(client)["csrf_token"]
    response = client.post("/api/tri/tab-token", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    principal = _read_session(client)["tri_principal"]
    assert principal and principal != PRE_LOGIN_PRINCIPAL


def test_failed_login_does_not_create_logged_in_session():
    client = _client({"csrf_token": PRE_LOGIN_CSRF})
    response = _login(client, password="wrong-password")
    assert response.headers["location"] == "/login?error=invalid"
    session = _read_session(client)
    assert "logged_in" not in session
    assert session.get("csrf_token") == PRE_LOGIN_CSRF


def test_login_with_bad_csrf_does_not_log_in():
    client = _client({"csrf_token": PRE_LOGIN_CSRF})
    response = _login(client, csrf="not-the-token")
    assert response.headers["location"] == "/login?error=csrf"
    assert "logged_in" not in _read_session(client)


# ---- 3. API key validation and CSRF ----

@pytest.mark.parametrize("value, expected", [
    (API_KEY, True),
    (PASSWORD_HASH, False),  # S4.2: the old hash-as-key is rejected
    ("", False),
    (None, False),
    ("wrong-key", False),
    (API_KEY + "x", False),
    ("é" * 10, False),
])
def test_is_valid_api_key(value, expected):
    assert auth.is_valid_api_key(value) is expected


def test_is_valid_api_key_false_when_not_configured(monkeypatch):
    monkeypatch.setattr(setup, "get_api_key", lambda: None)
    assert auth.is_valid_api_key("anything") is False


@pytest.mark.parametrize("headers", [
    {},
    {"X-API-Key": ""},
    {"X-API-Key": "bogus-key"},
])
def test_missing_empty_or_wrong_api_key_does_not_bypass_csrf(headers):
    client = _client(_logged_in())
    response = client.post("/logout", headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}
    assert _read_session(client)["logged_in"] is True  # the request never ran


def test_valid_api_key_skips_csrf_with_cookie_present():
    client = _client(_logged_in())
    assert client.post("/logout", headers={"X-API-Key": API_KEY}).status_code == 200


def test_valid_api_key_alone_authenticates_internal_calls():
    client = _client()
    assert client.post("/logout", headers={"X-API-Key": API_KEY}).status_code == 200


def test_wrong_api_key_alone_is_unauthenticated():
    client = _client()
    response = client.post("/logout", headers={"X-API-Key": "bogus-key"}, follow_redirects=False)
    assert response.status_code == 307


# ---- S4 interaction ----

def test_api_key_caller_is_denied_a_tri_tab_token():
    client = _client(_logged_in())
    response = client.post("/api/tri/tab-token", headers={"X-API-Key": API_KEY})
    assert response.status_code == 403
    assert response.json() == {"detail": chat_routes.TRI_TAB_TOKEN_DENIED_DETAIL}


def test_bogus_api_key_on_tab_token_hits_csrf_first():
    client = _client(_logged_in())
    response = client.post("/api/tri/tab-token", headers={"X-API-Key": "bogus-key"})
    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}


def test_tab_token_is_bound_to_the_minting_session():
    from core.des.web_tri_system import TRI_TAB_TOKEN_HEADER, get_web_tri_registry

    a = _client(_logged_in())
    token = a.post("/api/tri/tab-token", headers={"X-CSRF-Token": CSRF}).json()["token"]
    principal_a = _read_session(a)["tri_principal"]

    registry = get_web_tri_registry()
    assert registry._lookup(token, principal_a) is not None
    assert registry._lookup(token, "another-session-principal") is None

    class _Request:
        headers = {"X-API-Key": API_KEY, TRI_TAB_TOKEN_HEADER: token}
        session = {"logged_in": True, "tri_principal": principal_a}

    # A valid API key never reaches a tri flow, even with a bound token.
    result = registry.handle_request(_Request(), "tri")
    assert result.text is not None and "signed-in browser session" in result.text
