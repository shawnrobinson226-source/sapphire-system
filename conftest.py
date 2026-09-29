"""Repo-wide pytest setup.

S4.1: importing core.api_fastapi loads (and on first use creates) the session
signing secret. Point it at a throwaway directory before any test module is
imported so the suite never reads or writes the real user config directory.
"""

import os
import shutil
import tempfile

_SESSION_SECRET_DIR = None


def pytest_configure(config):
    global _SESSION_SECRET_DIR
    # Record (stat only, never contents) whether the real secret file exists, so
    # a test can prove the suite did not create or modify it.
    from core.setup import SESSION_SECRET_FILE

    try:
        stat = SESSION_SECRET_FILE.stat()
        state = f"present:{stat.st_mtime_ns}:{stat.st_size}"
    except FileNotFoundError:
        state = "absent"
    os.environ["SAPPHIRE_TEST_REAL_SESSION_SECRET_STATE"] = state
    _SESSION_SECRET_DIR = tempfile.mkdtemp(prefix="sapphire-test-session-secret-")
    os.environ["SAPPHIRE_SESSION_SECRET_FILE"] = os.path.join(_SESSION_SECRET_DIR, "session_secret")


def pytest_unconfigure(config):
    if _SESSION_SECRET_DIR:
        shutil.rmtree(_SESSION_SECRET_DIR, ignore_errors=True)
