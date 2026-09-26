"""Reusable offline guard for tests (S1.1 semantics).

tests/ is not a Python package, so a test module loads this file by path
(importlib) and registers the fixture by binding it at module level:

    no_network = _offline_guard.no_network

While the fixture is active, socket.socket.connect and connect_ex raise
(loopback included, e.g. DES on 127.0.0.1:8000). The one exception is
socket.socketpair(): on Windows it is Python's _fallback_socketpair, which
connects a loopback socket to itself, and asyncio calls it whenever an event
loop is created. A real connect is allowed only on the calling thread and only
while the guarded socketpair wrapper is running the real implementation; the
thread-local flag is cleared in ``finally``.
"""

import socket
import threading
import types

import pytest

_REAL_CONNECT = socket.socket.connect
SOCKETPAIR_GUARD = threading.local()

NETWORK_BLOCKED_MESSAGE = "network access attempted in an offline test"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Block connect/connect_ex, except connect inside the guarded socketpair.

    Returns the guard; ``guard.impl`` is the socketpair implementation the
    wrapper runs, so a test can force the fallback without replacing the wrapper.
    """

    def refuse(*args, **kwargs):
        raise AssertionError(NETWORK_BLOCKED_MESSAGE)

    def guarded_connect(self, *args, **kwargs):
        if getattr(SOCKETPAIR_GUARD, "active", False):
            return _REAL_CONNECT(self, *args, **kwargs)
        refuse()

    guard = types.SimpleNamespace(impl=socket.socketpair, wrapper=None)

    def guarded_socketpair(*args, **kwargs):
        SOCKETPAIR_GUARD.active = True
        try:
            return guard.impl(*args, **kwargs)
        finally:
            SOCKETPAIR_GUARD.active = False

    guard.wrapper = guarded_socketpair
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "socketpair", guarded_socketpair)
    return guard
