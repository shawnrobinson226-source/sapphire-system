import asyncio
import sys
from pathlib import Path

from core import api_fastapi
from core.des.tri_system_flow import TriSystemFlow
from core.des.web_tri_system import WebTriSystemBridge, resolve_web_operator_id

chat_routes = sys.modules["core.routes.chat"]
ROOT = Path(__file__).resolve().parents[1]


DES_RESULT = {
    "done": True,
    "friction_type": "information_gap",
    "output": {
        "output_type": "clarify",
    },
}


class FakeDESFlow:
    def __init__(self):
        self.answer_payloads = []

    def trigger(self, payload):
        return {"show": True}

    def start(self, payload):
        return {
            "interaction_id": "interaction-1",
            "question": {
                "id": "q1",
                "text": "Choose one.",
                "options": ["a"],
            },
        }

    def answer(self, payload):
        self.answer_payloads.append(payload)
        return DES_RESULT


def make_bridge(axis_calls=None):
    axis_calls = axis_calls if axis_calls is not None else []

    def axis_executor(**kwargs):
        axis_calls.append(kwargs)
        return {"ok": True, "sessionId": "axis-session"}, True

    def flow_factory():
        return TriSystemFlow(
            des_flow=FakeDESFlow(),
            health_check=lambda: {"ok": True},
            identity_resolver=lambda prompt=False: "operator-1",
            axis_executor=axis_executor,
        )

    return WebTriSystemBridge(flow_factory=flow_factory)


def test_normal_chat_is_not_intercepted():
    bridge = make_bridge()

    assert bridge.handle("hello Sapphire") is None
    assert bridge.handle("please start triage") is None
    assert bridge.handle("confirm") is None


def test_explicit_tri_start_returns_des_question():
    bridge = make_bridge()

    response = bridge.handle("/tri")

    assert "A few questions" in response
    assert "Choose one." in response
    assert bridge.active is True


def test_answer_renders_des_result_preview_and_pending_confirm():
    bridge = make_bridge()

    bridge.handle("tri")
    response = bridge.handle("a")

    assert "Decision Summary" in response
    assert "Proposed Action" in response
    assert "Proposed Action" in response
    assert "Type confirm to execute AXIS." in response
    assert "Type reject to cancel." in response
    assert bridge.active is True


def test_reject_clears_pending_without_axis_call():
    axis_calls = []
    bridge = make_bridge(axis_calls)

    bridge.handle("tri")
    bridge.handle("a")
    response = bridge.handle("reject")

    assert "Review Action" in response
    assert "Idle" in response
    assert bridge.active is False
    assert axis_calls == []


def test_confirm_executes_axis_once_and_deactivates_flow():
    axis_calls = []
    bridge = make_bridge(axis_calls)

    bridge.handle("tri")
    bridge.handle("a")
    response = bridge.handle("confirm")
    second = bridge.handle("confirm")

    assert "Action Result" in response
    assert "axis-session" in response
    assert len(axis_calls) == 1
    assert bridge.active is False
    assert second is None


def test_non_confirm_text_during_pending_does_not_execute_axis():
    axis_calls = []
    bridge = make_bridge(axis_calls)

    bridge.handle("tri")
    bridge.handle("a")
    response = bridge.handle("not yet")

    assert "confirmation pending" in response
    assert axis_calls == []
    assert bridge.active is True


def test_expired_pending_confirmation_blocks_axis_and_clears_flow():
    axis_calls = []
    bridge = make_bridge(axis_calls)

    bridge.handle("tri")
    bridge.handle("a")
    bridge.flow.pending_execution["expires_at"] = 0
    response = bridge.handle("confirm")

    assert "AXIS payload is not ready for execution." in response
    assert axis_calls == []
    assert bridge.active is False


def test_confirm_missing_operator_id_fails_closed_without_axis_call(monkeypatch):
    axis_calls = []
    identity_calls = []

    def fake_resolve_operator_id(prompt=False):
        identity_calls.append(prompt)
        return None

    monkeypatch.setattr(
        "core.des.web_tri_system.resolve_operator_id",
        fake_resolve_operator_id,
    )

    def flow_factory():
        return TriSystemFlow(
            des_flow=FakeDESFlow(),
            health_check=lambda: {"ok": True},
            identity_resolver=resolve_web_operator_id,
            axis_executor=lambda **kwargs: (axis_calls.append(kwargs) or {"ok": True}, True),
        )

    bridge = WebTriSystemBridge(flow_factory=flow_factory)
    bridge.handle("tri")
    bridge.handle("a")

    response = bridge.handle("confirm")

    assert identity_calls == [False]
    assert axis_calls == []
    assert "Review Action Error" in response
    assert "Missing operator_id. Execution stopped." in response
    assert bridge.active is False
    assert bridge.flow.pending_execution is None


def test_chat_route_returns_hybrid_response_before_normal_chat(monkeypatch):
    class FakeRequest:
        session = {"csrf_token": "test-session"}

        async def json(self):
            return {"text": "tri"}

    class FakeSystem:
        def __init__(self):
            self.normal_chat_calls = []

        def web_active_inc(self):
            self.normal_chat_calls.append("inc")

        def web_active_dec(self):
            self.normal_chat_calls.append("dec")

        def process_llm_query(self, text, skip_tts=False):
            self.normal_chat_calls.append(text)
            return "normal"

    class FakeBridge:
        def handle(self, text):
            assert text == "tri"
            return "hybrid response"

    system = FakeSystem()
    monkeypatch.setattr(chat_routes, "get_web_tri_system_bridge", lambda: FakeBridge())

    response = asyncio.run(chat_routes.handle_chat(FakeRequest(), _=None, system=system))

    assert response == {"response": "hybrid response"}
    assert system.normal_chat_calls == []


def test_hybrid_stream_completion_preserves_visible_response():
    chat_route = (ROOT / "core/routes/chat.py").read_text(encoding="utf-8")
    api_js = (ROOT / "interfaces/web/static/api.js").read_text(encoding="utf-8")
    ui_js = (ROOT / "interfaces/web/static/ui.js").read_text(encoding="utf-8")
    send_handlers = (ROOT / "interfaces/web/static/handlers/send-handlers.js").read_text(encoding="utf-8")

    assert "{'done': True, 'hybrid': True}" in chat_route
    assert "onDone(data.ephemeral || false, data.hybrid === true)" in api_js
    assert "finishStreaming = async (ephemeral = false, skipHistorySwap = false)" in ui_js
    assert "if (skipHistorySwap)" in ui_js
    assert "await ui.finishStreaming(false, hybrid === true);" in send_handlers
