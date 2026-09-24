"""Settings "Test AXIS Identity" button: message shown for each API response.

The behavioral tests execute the real system.js click handler under Node with
its imports stubbed; they skip only when Node is unavailable.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_JS = ROOT / "interfaces" / "web" / "static" / "views" / "settings-tabs" / "system.js"

NOT_CONFIGURED_TEXT = "Blocked — AXIS base URL is not configured"
ZERO_TOOLS_TEXT = "Blocked — zero-tools mode is active"

_HARNESS = r"""
import system from './views/settings-tabs/system.js';

const response = JSON.parse(process.argv[2]);
globalThis.__axisIdentityResponse = response;

function fakeElement() {
    const classes = new Set();
    return {
        style: {},
        textContent: '',
        className: '',
        classList: { add: (c) => classes.add(c), has: (c) => classes.has(c) },
        listeners: {},
        addEventListener(type, fn) { this.listeners[type] = fn; },
        classes,
    };
}

const button = fakeElement();
const result = fakeElement();
const el = {
    querySelector(selector) {
        if (selector === '#axis-identity-test') return button;
        if (selector === '#axis-identity-result') return result;
        return null;
    },
};

system.attachListeners({}, el);
await button.listeners.click();
console.log(JSON.stringify({ text: result.textContent, classes: [...result.classes] }));
"""

_SETTINGS_API_STUB = """
export async function testAxisIdentity() { return globalThis.__axisIdentityResponse; }
export async function getOperatorIdStatus() { return { status: 'missing', source: null }; }
export async function resetAllSettings() {}
export async function resetPrompts() {}
export async function mergeUpdates() {}
export async function resetChatDefaults() {}
"""


def _click_axis_identity_button(tmp_path, response):
    root = tmp_path / "static"
    (root / "views" / "settings-tabs").mkdir(parents=True)
    (root / "shared").mkdir()
    (root / "features").mkdir()
    (root / "views" / "settings-tabs" / "system.js").write_text(
        SYSTEM_JS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "shared" / "settings-api.js").write_text(_SETTINGS_API_STUB, encoding="utf-8")
    (root / "ui.js").write_text("export function showToast() {}\n", encoding="utf-8")
    (root / "features" / "scene.js").write_text("export function updateScene() {}\n", encoding="utf-8")
    (root / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    harness = root / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")

    completed = subprocess.run(
        ["node", str(harness), json.dumps(response)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=root,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@needs_node
def test_blocked_with_axis_not_configured_reason_shows_specific_message(tmp_path):
    shown = _click_axis_identity_button(tmp_path, {"status": "blocked", "reason": "axis_not_configured"})
    assert shown["text"] == NOT_CONFIGURED_TEXT
    assert "error" in shown["classes"]


@needs_node
@pytest.mark.parametrize(
    "response",
    [
        {"status": "blocked"},
        {"status": "blocked", "reason": "something_else"},
    ],
)
def test_other_blocked_responses_keep_zero_tools_message(tmp_path, response):
    shown = _click_axis_identity_button(tmp_path, response)
    assert shown["text"] == ZERO_TOOLS_TEXT


@needs_node
@pytest.mark.parametrize(
    "response, expected",
    [
        ({"status": "missing"}, "Operator ID missing"),
        ({"status": "success"}, "✓ AXIS confirmed operator identity"),
        ({"status": "offline"}, "✗ AXIS unreachable"),
        ({"status": "rejected"}, "✗ AXIS rejected the request"),
        ({"status": "offline", "reason": "axis_not_configured"}, "✗ AXIS unreachable"),
    ],
)
def test_other_status_messages_are_unchanged(tmp_path, response, expected):
    shown = _click_axis_identity_button(tmp_path, response)
    assert shown["text"] == expected


def test_system_tab_source_defines_not_configured_message_for_blocked_reason_only():
    source = SYSTEM_JS.read_text(encoding="utf-8")
    assert "AXIS base URL is not configured" in source
    assert "key === 'blocked' && data.reason === 'axis_not_configured'" in source
    assert "Blocked \\u2014 zero-tools mode is active" in source
