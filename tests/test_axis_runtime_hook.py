import hashlib
import importlib.util
import logging
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "plugins" / "axis_runtime" / "hooks" / "pre_chat.py"


class Event:
    def __init__(self, text, system=None):
        self.input = text
        self.skip_llm = False
        self.ephemeral = None
        self.stop_propagation = False
        self.response = None
        self.metadata = {"system": system} if system is not None else {}


class Response:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


def load_hook(tmp_path):
    spec = importlib.util.spec_from_file_location("axis_runtime_pre_chat_test", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE_DIR = tmp_path
    return module


def save_preview(module, system=None):
    module._save_state(
        system,
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
        },
    )


class ZeroToolsFunctionManager:
    current_toolset_name = "none"
    enabled_tools = []

    def is_zero_tools_mode(self):
        return True


class ZeroToolsSystem:
    class Chat:
        function_manager = ZeroToolsFunctionManager()

    llm_chat = Chat()


class FakeSessionManager:
    def __init__(self, active_chat_name):
        self.active_chat_name = active_chat_name


class FakeSystem:
    """Minimal system stub exposing llm_chat.session_manager.active_chat_name,
    the same indirection _resolve_chat_key reads (mirrors _is_zero_tools_mode's
    existing getattr-chain pattern into `system`)."""

    class Chat:
        pass

    def __init__(self, active_chat_name):
        self.llm_chat = FakeSystem.Chat()
        self.llm_chat.session_manager = FakeSessionManager(active_chat_name)


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

    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: "operator-1")
    monkeypatch.setattr(module.requests, "post", fake_post)

    event = Event("confirm")
    module.pre_chat(event)

    assert event.skip_llm is True
    assert event.stop_propagation is True
    assert calls == [
        {
            "url": "https://vanta-app-gilt.vercel.app/api/v2/execute",
            "headers": {
                "x-operator-id": "operator-1",
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
    assert not module._state_path(None).exists()


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

    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: "operator-1")
    monkeypatch.setattr(module.requests, "post", fake_post)

    event = Event("comfirm")
    module.pre_chat(event)

    assert len(calls) == 1
    assert calls[0]["headers"]["x-operator-id"] == "operator-1"
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
    assert not module._state_path(None).exists()


def test_reject_clears_state_without_axis_call(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: calls.append(kwargs))

    event = Event("reject")
    module.pre_chat(event)

    assert calls == []
    assert event.response == "AXIS execution rejected."
    assert not module._state_path(None).exists()


def test_axis_rejection_renders_failure_and_clears_state(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: "operator-1")
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
    assert not module._state_path(None).exists()


def test_success_missing_nested_fields_renders_raw_payload_and_clears_state(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: "operator-1")
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
    assert not module._state_path(None).exists()


def test_confirm_fails_closed_without_operator_identity(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: None)
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: calls.append(kwargs))

    event = Event("confirm")
    module.pre_chat(event)

    assert calls == []
    assert event.response == (
        "AXIS execution blocked: no operator identity configured. Execution stopped."
    )
    assert "Grim" not in event.response
    assert not module._state_path(None).exists()


def test_start_des_uses_configured_operator_id_not_grim(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: "operator-1")
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return Response(
            200,
            {
                "interaction_id": "int-1",
                "question": {"id": "q1", "text": "First question"},
            },
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    event = Event("AXIS: start something")
    module.pre_chat(event)

    assert len(calls) == 1
    assert calls[0]["url"] == f"{module.DES_BASE_URL}/interaction/start"
    assert calls[0]["json"]["user_id"] == "operator-1"
    assert calls[0]["json"]["user_id"] != "Grim"
    assert "First question" in event.response


def test_start_des_fails_closed_without_operator_identity(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: None)
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: calls.append(kwargs))

    event = Event("AXIS: start something")
    module.pre_chat(event)

    assert calls == []
    assert event.response == (
        "AXIS execution blocked: no operator identity configured. Execution stopped."
    )
    assert "Grim" not in event.response


def test_pending_preview_scoped_to_chat_name_does_not_leak_across_chats(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: "operator-1")

    system_a = FakeSystem("chat-a")
    system_b = FakeSystem("chat-b")

    save_preview(module, system=system_a)

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        return Response(
            200,
            {
                "ok": True,
                "data": {
                    "sessionId": "session-a",
                    "outcome": "reduced",
                    "continuity_before": 50,
                    "continuity_after": 52,
                    "protocol_output": "step output",
                },
            },
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    # Chat B has no pending preview of its own — "confirm" there must not
    # resolve chat A's pending preview.
    event_b = Event("confirm", system=system_b)
    module.pre_chat(event_b)

    assert calls == []
    assert event_b.response is None
    assert event_b.skip_llm is False

    # Chat A's own confirm still resolves its own preview correctly.
    event_a = Event("confirm", system=system_a)
    module.pre_chat(event_a)

    assert len(calls) == 1
    assert "sessionId: session-a" in event_a.response
    assert not module._state_path(system_a).exists()


def test_confirm_still_resolves_correct_chat_after_scoping(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    monkeypatch.setattr(module, "resolve_operator_id", lambda prompt=False: "operator-1")

    system_a = FakeSystem("chat-a")
    system_b = FakeSystem("chat-b")

    save_preview(module, system=system_a)
    save_preview(module, system=system_b)

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        return Response(
            200,
            {
                "ok": True,
                "data": {
                    "sessionId": "session-b",
                    "outcome": "reduced",
                    "continuity_before": 50,
                    "continuity_after": 52,
                    "protocol_output": "step output",
                },
            },
        )

    monkeypatch.setattr(module.requests, "post", fake_post)

    event_b = Event("confirm", system=system_b)
    module.pre_chat(event_b)

    assert len(calls) == 1
    assert "sessionId: session-b" in event_b.response
    assert not module._state_path(system_b).exists()

    # Chat A's independent pending preview is untouched by chat B's confirm.
    assert module._state_path(system_a).exists()
    state_a = module._load_state(system_a)
    assert state_a.get("phase") == "axis_preview"


def test_state_path_falls_back_to_default_key_without_session_manager(tmp_path):
    module = load_hook(tmp_path)

    path_no_system = module._state_path(None)
    path_zero_tools_system = module._state_path(ZeroToolsSystem())

    assert path_no_system == path_zero_tools_system
    assert path_no_system.parent == module.STATE_DIR

    expected = module.STATE_DIR / f"{hashlib.sha256(b'fallback:no_session').hexdigest()}.json"
    assert path_no_system == expected


def test_chat_name_is_hashed_for_state_filename(tmp_path, caplog):
    module = load_hook(tmp_path)

    hostile_name = "../../etc/passwd"
    system = FakeSystem(hostile_name)

    with caplog.at_level(logging.DEBUG, logger="axis_runtime_pre_chat_test"):
        path = module._state_path(system)

    assert hostile_name not in str(path)
    assert path.parent == module.STATE_DIR

    expected_hash = hashlib.sha256(f"chat:{hostile_name}".encode("utf-8")).hexdigest()
    assert path.name == f"{expected_hash}.json"

    assert any(hostile_name in m and expected_hash in m for m in caplog.messages)


def test_zero_tools_mode_prevents_axis_runtime_hook_execution(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    save_preview(module)
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: calls.append(kwargs))

    event = Event("confirm", system=ZeroToolsSystem())
    module.pre_chat(event)

    assert calls == []
    assert event.skip_llm is False
    assert event.stop_propagation is False
    assert event.response is None
    assert module._state_path(None).exists()


def test_zero_tools_mode_blocks_axis_runtime_final_execution_boundary(tmp_path, monkeypatch):
    module = load_hook(tmp_path)
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: calls.append(kwargs))

    result = module._execute_axis_preview(
        {
            "trigger": "des_decision_friction",
            "classification": "perceptual",
            "next_action": "Review the clarified decision information and choose one next step.",
            "reference": True,
            "stability": 6,
            "impact": 4,
        },
        system=ZeroToolsSystem(),
    )

    assert calls == []
    assert "AXIS Execution Rejected" in result
    assert "Zero tools mode is active" in result
    assert "AXIS Execution Complete" not in result


def test_zero_tools_global_system_blocks_axis_runtime_without_event_metadata(tmp_path, monkeypatch):
    from core import api_fastapi

    module = load_hook(tmp_path)
    save_preview(module)
    calls = []
    monkeypatch.setattr(module.requests, "post", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(api_fastapi, "_system", ZeroToolsSystem())

    event = Event("confirm")
    module.pre_chat(event)

    assert calls == []
    assert "Zero tools mode is active" in event.response
    assert "AXIS Execution Complete" not in event.response
    assert not module._state_path(None).exists()
