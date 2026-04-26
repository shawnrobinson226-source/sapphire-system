from core.des.axis_preview import build_axis_preview
from core.des.tri_system_flow import TriSystemFlow
from ui.app import SapphireUIApp
from ui.views import render_tri_state


DES_RESULT = {
    "done": True,
    "friction_type": "information_gap",
    "output": {
        "output_type": "clarify",
    },
}


class FakeDESFlow:
    def __init__(self, *, start_response=None, answer_response=None):
        self.trigger_payload = None
        self.start_payload = None
        self.answer_payload = None
        self.start_response = start_response
        self.answer_response = answer_response or DES_RESULT

    def trigger(self, payload):
        self.trigger_payload = payload
        return {"show": True}

    def start(self, payload):
        self.start_payload = payload
        if self.start_response is not None:
            return self.start_response
        return {
            "interaction_id": "interaction-1",
            "question": {
                "id": "q1",
                "text": "Choose one.",
                "options": ["a"],
            },
        }

    def answer(self, payload):
        self.answer_payload = payload
        return self.answer_response


def make_flow(fake_des=None, identity_resolver=None, axis_executor=None):
    return TriSystemFlow(
        des_flow=fake_des or FakeDESFlow(),
        health_check=lambda: {"ok": True},
        identity_resolver=identity_resolver or (lambda prompt=False: "operator-1"),
        axis_executor=axis_executor or (lambda **kwargs: ({"ok": True}, True)),
    )


def advance_to_preview(flow):
    question = flow.start()
    assert question["type"] == "question"
    result = flow.submit_answer("a")
    assert result["type"] == "result"
    return result


def test_question_state_shape():
    state = make_flow().start()

    assert state == {
        "type": "question",
        "data": {
            "id": "q1",
            "text": "Choose one.",
            "options": ["a"],
        },
    }


def test_invalid_unexpected_des_response_returns_error_state():
    flow = make_flow(FakeDESFlow(start_response={"question": {"id": "q1"}}))

    state = flow.start()

    assert state["type"] == "error"
    assert state["data"] == {
        "message": "DES returned an invalid question.",
        "recoverable": True,
    }


def test_cancel_does_not_read_identity():
    identity_calls = []

    def fail_identity(prompt=False):
        identity_calls.append(prompt)
        raise AssertionError("identity should not be read on cancel")

    flow = make_flow(identity_resolver=fail_identity)
    advance_to_preview(flow)

    state = flow.cancel()

    assert state == {"type": "idle", "data": {}}
    assert identity_calls == []


def test_confirm_reads_identity_and_calls_axis_once():
    identity_calls = []
    axis_calls = []

    def identity(prompt=False):
        identity_calls.append(prompt)
        return "operator-1"

    def axis(**kwargs):
        axis_calls.append(kwargs)
        return {"ok": True, "sessionId": "axis-session"}, True

    flow = make_flow(identity_resolver=identity, axis_executor=axis)
    advance_to_preview(flow)

    state = flow.confirm()

    assert state == {
        "type": "axis_result",
        "data": {"ok": True, "sessionId": "axis-session"},
    }
    assert identity_calls == [True]
    assert len(axis_calls) == 1
    assert axis_calls[0]["operator_id"] == "operator-1"


def test_axis_failure_renders_error_state():
    flow = make_flow(axis_executor=lambda **kwargs: ({"ok": False}, False))
    advance_to_preview(flow)

    state = flow.confirm()
    rendered = render_tri_state(state)

    assert state["type"] == "error"
    assert state["data"]["message"] == "AXIS execution failed."
    assert "Tri-System Error" in rendered
    assert "AXIS execution failed." in rendered


def test_no_operator_id_in_des_payloads():
    fake_des = FakeDESFlow()
    flow = make_flow(fake_des)

    advance_to_preview(flow)

    assert "operator_id" not in fake_des.trigger_payload
    assert "operator_id" not in fake_des.start_payload
    assert "operator_id" not in fake_des.answer_payload


def test_axis_payload_preview_does_not_include_operator_id():
    axis_payload = build_axis_preview(DES_RESULT)

    assert "operator_id" not in axis_payload


def test_tri_flow_mount_renders_result_preview_and_confirm():
    flow = make_flow()
    app = SapphireUIApp(tri_flow_factory=lambda: flow)

    state = app.start_tri_flow()
    assert state["type"] == "question"
    assert "Tri-System DES Question" in app.render()

    state = app.submit_tri_answer("a")
    rendered = app.render()

    assert state["type"] == "confirm"
    assert "Tri-System DES Result" in rendered
    assert "Tri-System AXIS Preview" in rendered
    assert "classification:" in rendered
    assert "next_action:" in rendered
    assert "Options: Confirm / Cancel" in rendered
