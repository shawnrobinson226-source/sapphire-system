"""S4.2: the internal API key is a dedicated random secret, not the password hash.

D1: startup fails if the key cannot be loaded or persisted.
D2: the password hash is rejected as an API key immediately.
D3: the key lives in its own protected file, read by the in-process caller.
"""

import os
import subprocess
import sys
from pathlib import Path

import bcrypt
import pytest

from core import auth, setup

ROOT = Path(__file__).resolve().parents[1]
PASSWORD_HASH = bcrypt.hashpw(b"s4-2-password", bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture
def key_file(tmp_path, monkeypatch):
    path = tmp_path / "cfg" / "api_key"
    monkeypatch.setenv(setup.API_KEY_PATH_ENV, str(path))
    monkeypatch.setattr(setup, "_api_key_cache", None)
    monkeypatch.setattr(setup, "get_password_hash", lambda: PASSWORD_HASH)
    return path


# ---- D3: separate persistent protected key ----

def test_key_is_created_once_and_persists(key_file):
    key = setup.get_api_key()
    assert key_file.read_text(encoding="ascii").strip() == key
    assert len(key) >= 64
    assert setup.load_or_create_api_key() == key


def test_key_is_independent_of_password_hash_and_session_secret(key_file, tmp_path):
    key = setup.get_api_key()
    assert key != PASSWORD_HASH
    assert key != setup.load_or_create_session_secret(tmp_path / "session_secret")


def test_key_survives_restart(key_file):
    key = setup.get_api_key()
    env = dict(os.environ, SAPPHIRE_API_KEY_FILE=str(key_file))
    result = subprocess.run(
        [sys.executable, "-c", "from core.setup import get_api_key; print(get_api_key())"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == key


def test_cached_key_does_not_change_if_file_is_replaced(key_file):
    key = setup.get_api_key()
    key_file.write_text("r" * 64, encoding="ascii")
    assert setup.get_api_key() == key


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_key_file_is_private_on_posix(key_file):
    setup.get_api_key()
    assert key_file.stat().st_mode & 0o077 == 0


def test_invalid_existing_key_fails_closed_and_is_not_overwritten(key_file):
    key_file.parent.mkdir(parents=True)
    key_file.write_text("short")
    with pytest.raises(setup.ApiKeyError):
        setup.get_api_key()
    assert key_file.read_text() == "short"


# ---- D2: old password hash rejected ----

def test_password_hash_is_not_a_valid_api_key(key_file):
    key = setup.get_api_key()
    assert auth.is_valid_api_key(key) is True
    assert auth.is_valid_api_key(PASSWORD_HASH) is False


def test_internal_caller_sends_the_new_key(key_file):
    from functions import meta

    headers = meta._get_api_headers()
    assert headers["X-API-Key"] == setup.get_api_key()
    assert headers["X-API-Key"] != PASSWORD_HASH
    assert auth.is_valid_api_key(headers["X-API-Key"]) is True


# ---- D1: startup fails closed ----

def test_unpersistable_key_raises(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    with pytest.raises(setup.ApiKeyError):
        setup.load_or_create_api_key(blocker / "api_key")


def test_app_import_fails_closed_when_key_cannot_be_persisted(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    env = dict(os.environ, SAPPHIRE_API_KEY_FILE=str(blocker / "api_key"))
    result = subprocess.run(
        [sys.executable, "-c", "import core.api_fastapi"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode != 0
    assert "ApiKeyError" in result.stderr
