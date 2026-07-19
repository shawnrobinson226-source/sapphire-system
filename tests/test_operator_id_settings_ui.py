"""Operator ID sensitive-settings masking and UI exposure tests."""

from unittest import mock

from fastapi.testclient import TestClient

from core.api_fastapi import app
from core.auth import require_login
from core.routes.settings import _SENSITIVE_KEYS
from core.settings_manager import settings

app.dependency_overrides[require_login] = lambda: None
client = TestClient(app)


def _set_operator_id(value):
    original = settings.get("OPERATOR_ID", "")
    settings.set("OPERATOR_ID", value, persist=False)
    return original


def _restore_operator_id(original):
    settings.set("OPERATOR_ID", original, persist=False)


def test_operator_id_is_sensitive():
    assert "OPERATOR_ID" in _SENSITIVE_KEYS


def test_bulk_settings_masks_operator_id():
    original = _set_operator_id("real-operator-value")
    try:
        response = client.get("/api/settings")
        assert response.status_code == 200
        assert response.json()["settings"]["OPERATOR_ID"] == "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
    finally:
        _restore_operator_id(original)


def test_single_setting_masks_operator_id():
    original = _set_operator_id("real-operator-value")
    try:
        response = client.get("/api/settings/OPERATOR_ID")
        assert response.status_code == 200
        assert response.json()["value"] == "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
    finally:
        _restore_operator_id(original)


def test_batch_update_does_not_overwrite_with_masked_placeholder():
    original = _set_operator_id("real-operator-value")
    try:
        with mock.patch("core.routes.settings.get_system", return_value=mock.Mock()):
            response = client.put(
                "/api/settings/batch",
                json={"settings": {"OPERATOR_ID": "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"}, "persist": False},
            )
        assert response.status_code == 200
        assert settings.get("OPERATOR_ID") == "real-operator-value"
    finally:
        _restore_operator_id(original)


def test_system_tab_declares_operator_id_essential():
    source = open("interfaces/web/static/views/settings-tabs/system.js", encoding="utf-8").read()
    assert "essentialKeys: ['OPERATOR_ID', 'WEB_UI_SSL_ADHOC']" in source


def test_operator_id_renders_as_password_input():
    source = open("interfaces/web/static/views/settings.js", encoding="utf-8").read()
    assert "if (key === 'OPERATOR_ID' || key.endsWith('_API_KEY')) {" in source
