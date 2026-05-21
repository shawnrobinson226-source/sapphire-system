import json
import asyncio
import sys

from core.chat.chat import LLMChat
from core.chat.history import ChatSessionManager
from core.chat.llm_providers import LLMResponse, ToolCall
from core.hooks import hook_runner


class FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, response=None, stream_events=None):
        self.response = response
        self.stream_events = stream_events or []
        self.tools_seen = []
        self.messages_seen = []

    def chat_completion(self, messages, tools=None, generation_params=None):
        self.messages_seen.append(messages)
        self.tools_seen.append(tools)
        return self.response

    def chat_completion_stream(self, messages, tools=None, generation_params=None):
        self.messages_seen.append(messages)
        self.tools_seen.append(tools)
        yield from self.stream_events

    def format_tool_result(self, tool_call_id, function_name, result):
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": function_name,
            "content": result,
        }


def make_chat(tmp_path, monkeypatch, provider):
    session_manager = ChatSessionManager(history_dir=str(tmp_path / "history"))
    chat = LLMChat(history=session_manager)
    chat.function_manager.update_enabled_functions(["none"])
    monkeypatch.setattr(chat, "_select_provider", lambda: ("fake", provider, ""))
    monkeypatch.setattr("core.chat.chat.get_generation_params", lambda *args, **kwargs: {})
    monkeypatch.setattr("core.chat.chat_streaming.get_generation_params", lambda *args, **kwargs: {})
    return chat


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
        self.active_count = 0

    def web_active_inc(self):
        self.active_count += 1

    def web_active_dec(self):
        self.active_count -= 1


class StaleAllToolsFunctionManager:
    current_toolset_name = "all"

    def __init__(self):
        self.enabled_tools = [{"function": {"name": "execute_axis"}}]

    def get_enabled_function_names(self):
        return ["execute_axis"]

    def is_zero_tools_mode(self):
        return False


class ZeroSettingsSessionManager:
    def get_chat_settings(self):
        return {"toolset": "none"}


class StaleAllToolsSystem:
    class Chat:
        function_manager = StaleAllToolsFunctionManager()
        session_manager = ZeroSettingsSessionManager()

    llm_chat = Chat()


class FakeRequest:
    session = {"csrf_token": "test-session"}

    def __init__(self, body=None):
        self.body = body or {"text": "Use execute_axis to run a trigger for Grim."}

    async def json(self):
        return self.body


async def collect_sse(response):
    chunks = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        chunks.append(chunk)
    return "".join(chunks)


def test_zero_tools_treats_execute_axis_text_call_as_plain_response(tmp_path, monkeypatch):
    text_call = json.dumps(
        {
            "function_call": {
                "name": "execute_axis",
                "arguments": {
                    "trigger": "des_decision_friction",
                    "classification": "narrative",
                    "next_action": "run",
                    "operator_id": "Grim",
                },
            }
        }
    )
    provider = FakeProvider(response=LLMResponse(content=text_call))
    chat = make_chat(tmp_path, monkeypatch, provider)

    execute_calls = []
    monkeypatch.setattr(
        chat.function_manager,
        "execute_function",
        lambda *args, **kwargs: execute_calls.append(args) or "should not run",
    )

    response = chat.chat("Use execute_axis to run a trigger for Grim.")

    assert response == "No tools are available in this mode. I cannot list, call, or execute tools."
    assert provider.tools_seen == []
    assert execute_calls == []
    assert chat.function_manager.is_zero_tools_mode() is True


def test_zero_tools_ignores_provider_native_execute_axis_tool_call(tmp_path, monkeypatch):
    provider = FakeProvider(
        response=LLMResponse(
            content="I cannot use tools in this mode.",
            tool_calls=[
                ToolCall(
                    id="call_axis",
                    name="execute_axis",
                    arguments=json.dumps({"trigger": "des_decision_friction"}),
                )
            ],
        )
    )
    chat = make_chat(tmp_path, monkeypatch, provider)

    execute_calls = []
    monkeypatch.setattr(
        chat.function_manager,
        "execute_function",
        lambda *args, **kwargs: execute_calls.append(args) or "should not run",
    )

    response = chat.chat("Use execute_axis to run a trigger for Grim.")

    assert response == "No tools are available in this mode. I cannot list, call, or execute tools."
    assert provider.tools_seen == []
    assert execute_calls == []


def test_zero_tools_stream_emits_no_tool_events_for_execute_axis(tmp_path, monkeypatch):
    provider = FakeProvider(
        stream_events=[
            {
                "type": "tool_call",
                "index": 0,
                "id": "call_axis",
                "name": "execute_axis",
                "arguments": json.dumps({"trigger": "des_decision_friction"}),
            },
            {"type": "content", "text": "Pure text only."},
            {"type": "done", "response": LLMResponse(content="Pure text only.")},
        ]
    )
    chat = make_chat(tmp_path, monkeypatch, provider)

    execute_calls = []
    monkeypatch.setattr(
        chat.function_manager,
        "execute_function",
        lambda *args, **kwargs: execute_calls.append(args) or "should not run",
    )

    events = list(chat.chat_stream("Use execute_axis to run a trigger for Grim."))
    event_types = [event.get("type") for event in events if isinstance(event, dict)]

    assert provider.tools_seen == []
    assert execute_calls == []
    assert "tool_pending" not in event_types
    assert "tool_start" not in event_types
    assert "tool_end" not in event_types
    assert {
        "type": "content",
        "text": "No tools are available in this mode. I cannot list, call, or execute tools.",
    } in events


def test_zero_tools_answers_list_tools_as_unavailable(tmp_path, monkeypatch):
    provider = FakeProvider(response=LLMResponse(content="should not be called"))
    chat = make_chat(tmp_path, monkeypatch, provider)

    response = chat.chat("list_tools")

    assert response == "No tools are available in this mode. I cannot list, call, or execute tools."
    assert provider.tools_seen == []


def test_zero_tools_omits_prior_tool_history_from_llm_context(tmp_path, monkeypatch):
    provider = FakeProvider(response=LLMResponse(content="Pure text only."))
    chat = make_chat(tmp_path, monkeypatch, provider)
    chat.session_manager.add_user_message("Use execute_axis to run a trigger for Grim.")
    chat.session_manager.add_assistant_with_tool_calls(
        "",
        [
            {
                "id": "call_axis",
                "type": "function",
                "function": {"name": "execute_axis", "arguments": "{}"},
            }
        ],
    )
    chat.session_manager.add_tool_result("call_axis", "list_tools", "execute_axis needs parameters")

    response = chat.chat("What can you do?")

    assert response == "Pure text only."
    sent_messages = provider.messages_seen[-1]
    assert all(message.get("role") != "tool" for message in sent_messages)
    assert all("tool_calls" not in message for message in sent_messages)
    assert "execute_axis needs parameters" not in json.dumps(sent_messages)


def test_zero_tools_provider_input_has_no_tool_prompt_or_stale_tool_text(tmp_path, monkeypatch):
    provider = FakeProvider(response=LLMResponse(content="Pure text only."))
    chat = make_chat(tmp_path, monkeypatch, provider)
    chat.set_system_prompt(
        "You are Sapphire.\n"
        "You have tools: execute_axis, list_tools, web search, and persistent memory.\n"
        "Keep replies concise."
    )
    chat.session_manager.add_assistant_final(
        "Enabled tools include list_tools and execute_axis. I need required parameters."
    )

    response = chat.chat("What can you do?")

    assert response == "Pure text only."
    sent_text = json.dumps(provider.messages_seen[-1]).lower()
    assert "execute_axis" not in sent_text
    assert "list_tools" not in sent_text
    assert "web search" not in sent_text
    assert "persistent memory" not in sent_text
    assert "enabled tools" not in sent_text
    assert "required parameters" not in sent_text
    assert "no tools are available in this mode" in sent_text


def test_web_stream_route_syncs_zero_tools_before_plugin_hooks(tmp_path, monkeypatch):
    from core import api_fastapi  # noqa: F401

    chat_routes = sys.modules["core.routes.chat"]

    hook_runner.clear()

    def axis_like_pre_chat(event):
        if "execute_axis" in event.input:
            event.skip_llm = True
            event.stop_propagation = True
            event.response = (
                "I need the trigger details:\n"
                "trigger:\n"
                "classification:\n"
                "next_action:\n"
                "operator_id: Grim"
            )

    hook_runner.register("pre_chat", axis_like_pre_chat, plugin_name="axis_runtime_test")

    provider = FakeProvider(
        stream_events=[
            {"type": "content", "text": "Pure assistant text only."},
            {"type": "done", "response": LLMResponse(content="Pure assistant text only.")},
        ]
    )
    chat = make_chat(tmp_path, monkeypatch, provider)
    chat.session_manager.update_chat_settings({"toolset": "none"})
    chat.function_manager.update_enabled_functions(["all"])

    def apply_only_toolset(system, settings):
        system.llm_chat.function_manager.update_enabled_functions([settings.get("toolset", "all")])

    class NoHybridBridge:
        def handle(self, text):
            return None

    monkeypatch.setattr(chat_routes, "_apply_chat_settings", apply_only_toolset)
    monkeypatch.setattr(chat_routes, "get_web_tri_system_bridge", lambda: NoHybridBridge())
    system = FakeWebSystem(chat)

    try:
        response = asyncio.run(chat_routes.handle_chat_stream(FakeRequest(), _=None, system=system))
        body = asyncio.run(collect_sse(response))
    finally:
        hook_runner.clear()

    assert provider.tools_seen == []
    assert "No tools are available in this mode" in body
    assert "I need the trigger details" not in body
    assert "tool_pending" not in body
    assert "tool_start" not in body
    assert "tool_end" not in body
    assert chat.function_manager.is_zero_tools_mode() is True


def test_toolset_activate_none_updates_runtime_and_active_chat_settings(tmp_path, monkeypatch):
    from core.routes import content as content_routes

    provider = FakeProvider()
    chat = make_chat(tmp_path, monkeypatch, provider)
    chat.session_manager.update_chat_settings({"toolset": "all"})
    chat.function_manager.update_enabled_functions(["all"])
    system = FakeWebSystem(chat)

    result = asyncio.run(content_routes.activate_toolset("none", FakeRequest(), _=None, system=system))

    assert result == {"status": "success", "toolset": "none"}
    assert chat.session_manager.get_chat_settings()["toolset"] == "none"
    assert chat.function_manager.is_zero_tools_mode() is True


def test_central_axis_guard_blocks_axis_tools_when_settings_are_zero_tools(monkeypatch):
    from core import api_fastapi
    from plugins.axis_integration import axis_tools

    calls = []
    monkeypatch.setattr(api_fastapi, "_system", StaleAllToolsSystem())
    monkeypatch.setattr(axis_tools.requests, "post", lambda *args, **kwargs: calls.append(kwargs))

    result, ok = axis_tools._execute_axis(
        trigger="des_decision_friction",
        operator_id="Grim",
        classification="perceptual",
        next_action="Review one step.",
        reference=True,
        stability=6,
        impact=4,
    )

    assert ok is False
    assert calls == []
    assert result["error"] == "AXIS execution blocked because Zero tools mode is active."
