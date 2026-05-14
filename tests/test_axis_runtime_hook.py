import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "plugins" / "axis_runtime" / "hooks" / "pre_chat.py"


class Event:
    def __init__(self, text):
        self.input = text
        self.skip_llm = False
        self.ephemeral = None
        self.stop_propagation = False
        self.response = None


class Response:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data


def load_hook(tmp_path):
    spec = importlib.util.spec_from_file_location("axis_runtime_pre_chat_test", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE_PATH = tmp_path / "axis_runtime_state.json"
    return module


def save_preview(module):
    module._save_state(
        {
            "active": True,
            "phase": "axis_preview",
            "preview": {
                "trigger": "des_decision_friction",
                "classification": "perceptual",
                "next_action": "Review the clarified decision information and choose one next step.",
                "reference": True,
                "stability": 6,
                "impact": 4,
                "des_metadata": {"must": "not-send"},
            },
        }
    )


def test_confirm_executes_saved_preview_with_axis_contract(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return Response(
            200,
            {
                "ok": True,
                "version": "v1",
                "data": {
                    "ok": True,
                    "sessionId": "session-1",
                    "outcome": "reduced",
                    "clarity_rating": 5,
                    "steps_completed": 9,
                    "continuity_before": 50.417,
                    "continuity_after": 52.611,
                    "protocol_output": "step output",
                },
            },
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    event = Event("confirm")
    module.pre_chat(event)

    assert event.skip_llm is True
    assert event.stop_propagation is True
    assert calls == [
        {
            "url": "https://vanta-app-gilt.vercel.app/api/v2/execute",
            "headers": {
                "x-operator-id": "Grim",
                "content-type": "application/json",
            },
            "json": {
                "trigger": "des_decision_friction",
                "classification": "perceptual",
                "next_action": "Review the clarified decision information and choose one next step.",
                "outcome": "reduced",
                "reference": True,
                "stability": 6,
                "impact": 4,
            },
            "timeout": 20,
        }
    ]
    assert "operator_id" not in calls[0]["json"]
    assert "des_metadata" not in calls[0]["json"]
    assert "sessionId: session-1" in event.response
    assert "outcome: reduced" in event.response
    assert "continuity_before: 50" in event.response
    assert "continuity_after: 53" in event.response
    assert "protocol_output: step output" in event.response
    assert not module.STATE_PATH.exists()


def test_comfirm_executes_saved_preview_with_axis_contract(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return Response(
            200,
            {
                "ok": True,
                "data": {
                    "ok": True,
                    "sessionId": "session-typo",
                    "outcome": "reduced",
                    "continuity_before": 50,
                    "continuity_after": 52,
                    "protocol_output": "step output",
                },
            },
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    event = Event("comfirm")
    module.pre_chat(event)

    assert len(calls) == 1
    assert calls[0]["json"] == {
        "trigger": "des_decision_friction",
        "classification": "perceptual",
        "next_action": "Review the clarified decision information and choose one next step.",
        "outcome": "reduced",
        "reference": True,
        "stability": 6,
        "impact": 4,
    }
    assert "sessionId: session-typo" in event.response
    assert not module.STATE_PATH.exists()


def test_reject_clears_state_without_axis_call(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: calls.append(kwargs))

    event = Event("reject")
    module.pre_chat(event)

    assert calls == []
    assert event.response == "AXIS execution rejected."
    assert not module.STATE_PATH.exists()


def test_axis_rejection_renders_failure_and_clears_state(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *args, **kwargs: Response(400, {"message": "unknown fields rejected"}),
    )

    event = Event("confirm")
    module.pre_chat(event)

    assert "AXIS Execution Rejected" in event.response
    assert "status_code: 400" in event.response
    assert "unknown fields rejected" in event.response
    assert not module.STATE_PATH.exists()


def test_success_missing_nested_fields_renders_raw_payload_and_clears_state(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *args, **kwargs: Response(200, {"ok": True, "data": {"sessionId": "session-1"}}),
    )

    event = Event("confirm")
    module.pre_chat(event)

    assert "AXIS Execution Rejected" in event.response
    assert "AXIS response missing fields" in event.response
    assert "raw_json:" in event.response
    assert "session-1" in event.response
    assert "outcome: None" not in event.response
    assert not module.STATE_PATH.exists()
