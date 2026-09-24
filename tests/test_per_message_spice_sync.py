"""Per-message chat-settings sync must not re-apply the spice set.

Regression: _sync_active_chat_settings (run by /api/chat and /api/chat/stream)
called the full _apply_chat_settings, which re-applied the chat's spice set,
rewrote user/prompts/prompt_spices.json and undid Spice Manager category
toggles on every message. It must still enforce the toolset / zero-tools mode.

All spice reads/writes go to a temporary copy; the repo's user/ files are never
touched. Routes are driven directly with a real LLMChat and a fake provider.
"""

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from core import api_fastapi  # noqa: F401  (app import order: routes import api_fastapi)
from core import prompts
from core.chat.chat import LLMChat
from core.chat.history import ChatSessionManager
from core.chat.llm_providers import LLMResponse
from core.routes import chat as chat_routes
from core.routes import content as content_routes

ROOT = Path(__file__).resolve().parents[1]
TRACKED_SPICES = ROOT / "user" / "prompts" / "prompt_spices.json"


class FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self):
        self.tools_seen = []

    def chat_completion(self, messages, tools=None, generation_params=None):
        self.tools_seen.append(tools)
        return LLMResponse(content="Plain reply.")

    def chat_completion_stream(self, messages, tools=None, generation_params=None):
        self.tools_seen.append(tools)
        yield {"type": "content", "text": "Plain reply."}
        yield {"type": "done", "response": LLMResponse(content="Plain reply.")}

    def format_tool_result(self, tool_call_id, function_name, result):
        return {"role": "tool", "tool_call_id": tool_call_id, "name": function_name, "content": result}


class FakeTTS:
    def set_voice(self, voice):
        self.voice = voice

    def set_pitch(self, pitch):
        self.pitch = pitch

    def set_speed(self, speed):
        self.speed = speed


class FakeWebSystem:
    def __init__(self, chat):
        self.llm_chat = chat
        self.tts = FakeTTS()

    def web_active_inc(self):
        pass

    def web_active_dec(self):
        pass

    def process_llm_query(self, text, from_web=False):
        return self.llm_chat.chat(text)


class FakeRequest:
    session = {"csrf_token": "test-session"}
    headers = {}

    def __init__(self, text="hello"):
        self.body = {"text": text}

    async def json(self):
        return self.body


class NoHybridBridge:
    def handle(self, text):
        return None


async def _collect_sse(response):
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


@pytest.fixture
def spice_file(tmp_path, monkeypatch):
    """Point the live PromptManager at a temp copy of the tracked spice file."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    shutil.copy2(TRACKED_SPICES, prompts_dir / "prompt_spices.json")
    from core.spice_sets import spice_set_manager

    monkeypatch.setattr(spice_set_manager, "_active_name", spice_set_manager._active_name)
    pm = prompts.prompt_manager
    for attr in ("USER_DIR", "_spices", "_spice_meta", "_disabled_categories"):
        monkeypatch.setattr(pm, attr, getattr(pm, attr))
    pm.USER_DIR = prompts_dir
    pm._load_spices()
    return prompts_dir / "prompt_spices.json"


class _WordTokenizer:
    """Offline stand-in for the tiktoken encoding (its download is not available in tests)."""

    def encode(self, text):
        return text.split()


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr("core.chat.history._tokenizer", _WordTokenizer())
    provider = FakeProvider()
    chat = LLMChat(history=ChatSessionManager(history_dir=str(tmp_path / "history")))
    monkeypatch.setattr(chat, "_select_provider", lambda: ("fake", provider, ""))
    monkeypatch.setattr("core.chat.chat.get_generation_params", lambda *a, **k: {})
    monkeypatch.setattr("core.chat.chat_streaming.get_generation_params", lambda *a, **k: {})
    monkeypatch.setattr(chat_routes, "get_web_tri_system_bridge", lambda: NoHybridBridge())
    monkeypatch.setattr(chat_routes, "check_endpoint_rate", lambda *a, **k: None)
    # Active chat uses the "default" spice set, which enables every category but flirty.
    chat.session_manager.update_chat_settings({"spice_set": "default", "toolset": "none"})
    return FakeWebSystem(chat), provider


def _send(system, route, text="hello"):
    if route == "chat":
        return asyncio.run(chat_routes.handle_chat(FakeRequest(text), _=None, system=system))
    response = asyncio.run(chat_routes.handle_chat_stream(FakeRequest(text), _=None, system=system))
    return asyncio.run(_collect_sse(response))


@pytest.mark.parametrize("route", ["chat", "stream"])
def test_message_preserves_manually_disabled_category_and_spice_file(route, spice_file, web):
    system, _ = web
    pm = prompts.prompt_manager
    pm.set_category_enabled("scifi", False)  # operator choice in Spice Manager
    before_bytes = spice_file.read_bytes()
    before_disabled = set(pm.disabled_categories)
    assert "scifi" in before_disabled and len(before_disabled) > 1

    _send(system, route)
    _send(system, route, "second message")

    assert spice_file.read_bytes() == before_bytes
    assert set(pm.disabled_categories) == before_disabled
    assert json.loads(spice_file.read_text(encoding="utf-8"))["_disabled_categories"] == sorted(before_disabled)


@pytest.mark.parametrize("route", ["chat", "stream"])
def test_zero_tools_mode_is_enforced_on_every_message(route, spice_file, web):
    system, provider = web
    fm = system.llm_chat.function_manager

    fm.update_enabled_functions(["all"])  # stale runtime state
    _send(system, route)
    assert fm.is_zero_tools_mode() is True
    assert provider.tools_seen and all(not tools for tools in provider.tools_seen)

    # Chat settings change away from zero tools, then back: each message follows the saved toolset.
    system.llm_chat.session_manager.update_chat_settings({"toolset": "all"})
    _send(system, route, "second message")
    assert fm.current_toolset_name == "all"
    assert fm.is_zero_tools_mode() is False

    system.llm_chat.session_manager.update_chat_settings({"toolset": "none"})
    fm.update_enabled_functions(["all"])
    provider.tools_seen.clear()
    _send(system, route, "third message")
    assert fm.is_zero_tools_mode() is True
    assert all(not tools for tools in provider.tools_seen)


def test_operator_spice_set_activation_still_applies_the_set(spice_file, web):
    system, _ = web
    pm = prompts.prompt_manager
    pm.set_category_enabled("scifi", False)

    result = asyncio.run(content_routes.activate_spice_set("professional", FakeRequest(), _=None, system=system))

    assert result == {"status": "success", "spice_set": "professional"}
    from core.spice_sets import spice_set_manager

    expected_disabled = set(pm.spices) - set(spice_set_manager.get_categories("professional"))
    assert set(pm.disabled_categories) == expected_disabled
    assert set(json.loads(spice_file.read_text(encoding="utf-8"))["_disabled_categories"]) == expected_disabled
    assert system.llm_chat.session_manager.get_chat_settings()["spice_set"] == "professional"


def test_operator_settings_apply_path_still_applies_spice_set(spice_file, web):
    system, _ = web
    pm = prompts.prompt_manager
    pm.set_category_enabled("scifi", False)

    api_fastapi._apply_chat_settings(system, {"spice_set": "default"})

    assert set(pm.disabled_categories) == {"flirty"}
    assert json.loads(spice_file.read_text(encoding="utf-8"))["_disabled_categories"] == ["flirty"]
