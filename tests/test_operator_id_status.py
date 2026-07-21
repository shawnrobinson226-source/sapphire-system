"""Operator ID status endpoint — must agree with the real resolution chain."""

import logging
import os
from unittest import mock

from fastapi.testclient import TestClient

from core.api_fastapi import app
from core.auth import require_login
from core.identity.operator import resolve_operator_id
from core.settings_manager import settings

app.dependency_overrides[require_login] = lambda: None
client = TestClient(app)


def _restore_operator_id(original):
    settings.set("OPERATOR_ID", original, persist=False)


def test_status_missing_when_nothing_configured():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "", persist=False)
    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)
            response = client.get("/api/settings/operator-id/status")
        assert response.status_code == 200
        assert response.json() == {"status": "missing", "source": None}
        assert resolve_operator_id(prompt=False) is None
    finally:
        _restore_operator_id(original)


def test_status_configured_from_settings():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)
    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)
            response = client.get("/api/settings/operator-id/status")
        assert response.status_code == 200
        assert response.json() == {"status": "configured", "source": "settings"}
        assert resolve_operator_id(prompt=False) == "valid-operator"
    finally:
        _restore_operator_id(original)


def test_status_configured_from_environment_takes_precedence():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "settings-value", persist=False)
    try:
        with mock.patch.dict(os.environ, {"SAPPHIRE_OPERATOR_ID": "env-value"}):
            response = client.get("/api/settings/operator-id/status")
        assert response.status_code == 200
        assert response.json() == {"status": "configured", "source": "environment"}
    finally:
        _restore_operator_id(original)


def test_status_agrees_with_resolver_when_environment_is_whitespace_only():
    """Regression: an earlier draft reported 'invalid' here by checking the
    raw env var truthiness before stripping, while the real resolution chain
    (via the lenient validator) correctly falls through to settings. The
    status endpoint must agree with what actually resolves."""
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)
    try:
        with mock.patch.dict(os.environ, {"SAPPHIRE_OPERATOR_ID": "   "}):
            response = client.get("/api/settings/operator-id/status")
            resolved = resolve_operator_id(prompt=False)
        assert response.status_code == 200
        assert response.json() == {"status": "configured", "source": "settings"}
        assert resolved == "valid-operator"
    finally:
        _restore_operator_id(original)


def test_status_invalid_when_settings_value_fails_save_validation():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "bad\x00value", persist=False)
    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)
            response = client.get("/api/settings/operator-id/status")
        assert response.status_code == 200
        assert response.json() == {"status": "invalid", "source": "settings"}
    finally:
        _restore_operator_id(original)


def test_settings_api_exposes_operator_id_status_helper():
    source = open(
        "interfaces/web/static/shared/settings-api.js",
        encoding="utf-8",
    ).read()

    assert "export async function getOperatorIdStatus()" in source
    assert "fetchWithTimeout('/api/settings/operator-id/status')" in source


def test_system_tab_renders_operator_id_status_panel():
    source = open(
        "interfaces/web/static/views/settings-tabs/system.js",
        encoding="utf-8",
    ).read()

    assert 'id="operator-id-status"' in source
    assert "this.refreshOperatorIdStatus(el);" in source
    assert "const data = await getOperatorIdStatus();" in source


def test_system_tab_exposes_all_operator_id_status_states():
    source = open(
        "interfaces/web/static/views/settings-tabs/system.js",
        encoding="utf-8",
    ).read()

    assert "Configured — environment override" in source
    assert "Configured — local setting" in source
    assert "Invalid Operator ID" in source
    assert "Operator ID missing" in source
    assert "Unable to check Operator ID status" in source


def test_operator_id_status_ui_does_not_render_identity_value():
    source = open(
        "interfaces/web/static/views/settings-tabs/system.js",
        encoding="utf-8",
    ).read()

    assert "data.operator_id" not in source
    assert "data.value" not in source
    assert "${data" not in source


def test_axis_identity_missing_does_not_call_axis():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "", persist=False)

    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)

            with mock.patch(
                "core.sapphire.axis_execution_guard.assert_axis_execution_allowed"
            ) as guard:
                with mock.patch(
                    "plugins.axis_integration.axis_tools._fetch_axis_operator_profile"
                ) as fetch_profile:
                    response = client.post(
                        "/api/settings/operator-id/test-axis-identity"
                    )

        assert response.status_code == 200
        assert response.json() == {"status": "missing"}
        guard.assert_not_called()
        fetch_profile.assert_not_called()
    finally:
        _restore_operator_id(original)


def test_axis_identity_blocked_does_not_call_axis():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)

    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)

            with mock.patch(
                "core.sapphire.axis_execution_guard.assert_axis_execution_allowed",
                return_value=(False, {"error": "blocked"}),
            ):
                with mock.patch(
                    "plugins.axis_integration.axis_tools._fetch_axis_operator_profile"
                ) as fetch_profile:
                    response = client.post(
                        "/api/settings/operator-id/test-axis-identity"
                    )

        assert response.status_code == 200
        assert response.json() == {"status": "blocked"}
        fetch_profile.assert_not_called()
    finally:
        _restore_operator_id(original)


def test_axis_identity_success_calls_endpoint_once_and_returns_ui_safe_status():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)

    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)

            with mock.patch(
                "core.sapphire.axis_execution_guard.assert_axis_execution_allowed",
                return_value=(True, {}),
            ):
                with mock.patch(
                    "plugins.axis_integration.axis_tools._fetch_axis_operator_profile",
                    return_value=(
                        {"operator_id": "secret-value", "profile": {"name": "hidden"}},
                        True,
                    ),
                ) as fetch_profile:
                    response = client.post(
                        "/api/settings/operator-id/test-axis-identity"
                    )

        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        fetch_profile.assert_called_once_with("valid-operator")
    finally:
        _restore_operator_id(original)


def test_axis_identity_network_failure_returns_offline():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)

    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)

            with mock.patch(
                "core.sapphire.axis_execution_guard.assert_axis_execution_allowed",
                return_value=(True, {}),
            ):
                with mock.patch(
                    "plugins.axis_integration.axis_tools._fetch_axis_operator_profile",
                    return_value=(
                        {
                            "status_code": None,
                            "error": "connection details must not escape",
                        },
                        False,
                    ),
                ):
                    response = client.post(
                        "/api/settings/operator-id/test-axis-identity"
                    )

        assert response.status_code == 200
        assert response.json() == {"status": "offline"}
    finally:
        _restore_operator_id(original)


def test_axis_identity_http_failure_returns_rejected():
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)

    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)

            with mock.patch(
                "core.sapphire.axis_execution_guard.assert_axis_execution_allowed",
                return_value=(True, {}),
            ):
                with mock.patch(
                    "plugins.axis_integration.axis_tools._fetch_axis_operator_profile",
                    return_value=(
                        {
                            "status_code": 401,
                            "error": "raw AXIS response must not escape",
                        },
                        False,
                    ),
                ):
                    response = client.post(
                        "/api/settings/operator-id/test-axis-identity"
                    )

        assert response.status_code == 200
        assert response.json() == {"status": "rejected"}
    finally:
        _restore_operator_id(original)


def test_axis_identity_unexpected_exception_returns_offline_without_leaking_details(caplog):
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", "valid-operator", persist=False)

    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAPPHIRE_OPERATOR_ID", None)

            with mock.patch(
                "core.sapphire.axis_execution_guard.assert_axis_execution_allowed",
                return_value=(True, {}),
            ):
                with mock.patch(
                    "plugins.axis_integration.axis_tools._fetch_axis_operator_profile",
                    side_effect=RuntimeError("secret internal detail must not leak"),
                ):
                    with caplog.at_level(logging.WARNING):
                        response = client.post(
                            "/api/settings/operator-id/test-axis-identity"
                        )

        assert response.status_code == 200
        assert response.json() == {"status": "offline"}
        assert "secret internal detail" not in caplog.text
        assert "valid-operator" not in caplog.text
    finally:
        _restore_operator_id(original)


def test_settings_api_exposes_test_axis_identity_helper():
    source = open(
        "interfaces/web/static/shared/settings-api.js",
        encoding="utf-8",
    ).read()

    assert "export async function testAxisIdentity()" in source
    assert "fetchWithTimeout('/api/settings/operator-id/test-axis-identity'" in source
    assert "method: 'POST'" in source


def test_system_tab_renders_axis_identity_test_controls():
    source = open(
        "interfaces/web/static/views/settings-tabs/system.js",
        encoding="utf-8",
    ).read()

    assert 'id="axis-identity-test"' in source
    assert 'id="axis-identity-result"' in source
    assert "const data = await testAxisIdentity();" in source


def test_system_tab_exposes_all_axis_identity_result_states():
    source = open(
        "interfaces/web/static/views/settings-tabs/system.js",
        encoding="utf-8",
    ).read()

    assert "Operator ID missing" in source
    assert "zero-tools mode is active" in source
    assert "AXIS confirmed operator identity" in source
    assert "AXIS unreachable" in source
    assert "AXIS rejected the request" in source


def test_axis_identity_ui_does_not_render_raw_response_or_identity():
    source = open(
        "interfaces/web/static/views/settings-tabs/system.js",
        encoding="utf-8",
    ).read()

    assert "data.operator_id" not in source
    assert "data.profile" not in source
    assert "${data" not in source
    assert "e.message" not in source
