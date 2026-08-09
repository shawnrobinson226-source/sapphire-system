"""Privacy-mode network boundary: is_allowed_endpoint + privacy state.

The privacy whitelist is the egress trust boundary — a false-allow leaks chat
content to a non-whitelisted host, a false-block breaks legitimate local use,
and resolution failures must fail closed. These paths had zero coverage.

All tests are hermetic: socket.gethostbyname is always mocked, so no real DNS
lookup ever happens. Pre-DNS branches assert the resolver is never called;
DNS-path branches assert the exact lookup and stub its result.
"""

import socket
from unittest import mock

import pytest

import core.privacy as privacy


class _FakeSettings:
    """Minimal stand-in for core.settings_manager.settings (get/set only)."""

    def __init__(self, data):
        self.data = dict(data)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, persist=True):
        self.data[key] = value


@pytest.fixture(autouse=True)
def _isolate_hostname_cache():
    """Keep the module-global resolution cache from leaking across tests."""
    privacy._hostname_cache.clear()
    yield
    privacy._hostname_cache.clear()


def _install_settings(monkeypatch, *, privacy_mode, whitelist=None):
    data = {"PRIVACY_MODE": privacy_mode}
    if whitelist is not None:
        data["PRIVACY_NETWORK_WHITELIST"] = whitelist
    fake = _FakeSettings(data)
    # privacy.py does `from core.settings_manager import settings` inside each
    # function, so patching the module singleton is picked up at call time.
    monkeypatch.setattr("core.settings_manager.settings", fake)
    return fake


def _no_dns(monkeypatch):
    """Install a resolver that fails the test if DNS is ever consulted."""
    dns = mock.Mock(side_effect=AssertionError("socket.gethostbyname must not be called"))
    monkeypatch.setattr(privacy.socket, "gethostbyname", dns)
    return dns


def _stub_dns(monkeypatch, resolver):
    dns = mock.Mock(side_effect=resolver) if callable(resolver) else mock.Mock(return_value=resolver)
    monkeypatch.setattr(privacy.socket, "gethostbyname", dns)
    return dns


def test_privacy_off_bypasses_all_checks(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=False)
    dns = _no_dns(monkeypatch)

    assert privacy.is_allowed_endpoint("http://external.example.com/path") is True
    assert privacy.is_allowed_endpoint("8.8.8.8") is True
    dns.assert_not_called()


def test_whitelisted_hostname_allowed_without_dns(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["localhost", "10.0.0.0/8"])
    dns = _no_dns(monkeypatch)

    assert privacy.is_allowed_endpoint("http://localhost:8000/api") is True
    dns.assert_not_called()


def test_hostname_match_is_case_insensitive(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["Localhost"])
    dns = _no_dns(monkeypatch)

    assert privacy.is_allowed_endpoint("http://LOCALHOST:8000") is True
    dns.assert_not_called()


def test_ip_within_cidr_allowed_without_dns(monkeypatch):
    _install_settings(
        monkeypatch, privacy_mode=True, whitelist=["192.168.0.0/16", "172.16.0.0/12"]
    )
    dns = _no_dns(monkeypatch)

    assert privacy.is_allowed_endpoint("http://192.168.1.50:9000") is True
    assert privacy.is_allowed_endpoint("172.20.5.5") is True
    dns.assert_not_called()


def test_ip_outside_whitelist_blocked(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["192.168.0.0/16"])
    # gethostbyname on an IP literal returns the IP unchanged; stub keeps it hermetic.
    dns = _stub_dns(monkeypatch, "8.8.8.8")

    assert privacy.is_allowed_endpoint("http://8.8.8.8:443") is False
    dns.assert_called_once_with("8.8.8.8")


def test_hostname_resolving_to_whitelisted_ip_allowed(monkeypatch):
    # Single-IP whitelist entry also exercises the non-CIDR compare branch.
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["10.0.0.5"])
    dns = _stub_dns(monkeypatch, "10.0.0.5")

    assert privacy.is_allowed_endpoint("http://internal.service.local") is True
    dns.assert_called_once_with("internal.service.local")


def test_hostname_resolving_to_non_whitelisted_ip_blocked(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["10.0.0.0/8"])
    dns = _stub_dns(monkeypatch, "203.0.113.9")

    assert privacy.is_allowed_endpoint("http://exfil.example.com") is False
    dns.assert_called_once_with("exfil.example.com")


def test_unresolvable_hostname_fails_closed(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["10.0.0.0/8"])
    _stub_dns(monkeypatch, socket.gaierror("name resolution failed"))

    assert privacy.is_allowed_endpoint("http://does-not-resolve.invalid") is False


def test_hostless_or_empty_endpoint_fails_closed(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["10.0.0.0/8"])
    dns = _no_dns(monkeypatch)

    assert privacy.is_allowed_endpoint("http://") is False
    assert privacy.is_allowed_endpoint("") is False
    dns.assert_not_called()


def test_dns_resolution_is_cached(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["10.0.0.0/8"])
    dns = _stub_dns(monkeypatch, "10.0.0.42")

    assert privacy.is_allowed_endpoint("http://cached.host.local") is True
    assert privacy.is_allowed_endpoint("http://cached.host.local/other") is True
    dns.assert_called_once_with("cached.host.local")


def test_default_whitelist_applies_when_unset(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True)  # no PRIVACY_NETWORK_WHITELIST
    dns = _stub_dns(monkeypatch, "8.8.8.8")

    assert privacy.get_whitelist() == [
        "127.0.0.1",
        "localhost",
        "192.168.0.0/16",
        "10.0.0.0/8",
        "172.16.0.0/12",
    ]
    assert privacy.is_allowed_endpoint("http://127.0.0.1:8000") is True
    assert privacy.is_allowed_endpoint("http://8.8.8.8") is False


def test_set_privacy_mode_toggles_and_clears_cache(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=False)
    privacy._hostname_cache["stale.host"] = "1.2.3.4"

    changed = privacy.set_privacy_mode(True)

    assert changed is True
    assert privacy.is_privacy_mode() is True
    assert privacy._hostname_cache == {}


def test_set_privacy_mode_noop_when_unchanged(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True)
    privacy._hostname_cache["kept.host"] = "10.0.0.1"

    changed = privacy.set_privacy_mode(True)

    assert changed is False
    assert privacy._hostname_cache == {"kept.host": "10.0.0.1"}


def test_get_privacy_status_reports_state(monkeypatch):
    _install_settings(monkeypatch, privacy_mode=True, whitelist=["10.0.0.0/8", "localhost"])

    assert privacy.get_privacy_status() == {
        "enabled": True,
        "whitelist": ["10.0.0.0/8", "localhost"],
    }
