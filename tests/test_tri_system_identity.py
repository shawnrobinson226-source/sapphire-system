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


class NonPersistingDESFlow(FakeDESFlow):
    def answer(self, payload):
        self.answer_payload = {"question_id": payload.get("question_id")}
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


def test_des_offline_fails_closed_without_starting_flow():
    fake_des = FakeDESFlow()
    flow = TriSystemFlow(
        des_flow=fake_des,
        health_check=lambda: {"error": "offline"},
        identity_resolver=lambda prompt=False: "operator-1",
        axis_executor=lambda **kwargs: ({"ok": True}, True),
    )

    state = flow.start()

    assert state == {
        "type": "error",
        "data": {
            "message": "DES unavailable.",
            "recoverable": True,
        },
    }
    assert fake_des.trigger_payload is None
    assert fake_des.start_payload is None


def test_invalid_des_answer_response_stops_flow():
    flow = make_flow(FakeDESFlow(answer_response={"unexpected": True}))

    flow.start()
    state = flow.submit_answer("a")

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


def test_operator_selects_no_makes_no_axis_call():
    axis_calls = []

    flow = make_flow(axis_executor=lambda **kwargs: (axis_calls.append(kwargs) or {"ok": True}, True))
    advance_to_preview(flow)

    state = flow.cancel()

    assert state == {"type": "idle", "data": {}}
    assert axis_calls == []


def test_des_never_calls_axis_directly_before_confirmation():
    axis_calls = []

    flow = make_flow(axis_executor=lambda **kwargs: (axis_calls.append(kwargs) or {"ok": True}, True))
    advance_to_preview(flow)

    assert axis_calls == []
    assert flow.confirm_state()["type"] == "confirm"
    assert axis_calls == []


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


def test_missing_operator_id_prompt_occurs_only_after_confirmation():
    identity_calls = []

    def missing_identity(prompt=False):
        identity_calls.append(prompt)
        return None

    flow = make_flow(identity_resolver=missing_identity)
    advance_to_preview(flow)

    assert identity_calls == []
    assert flow.confirm_state()["type"] == "confirm"
    assert identity_calls == []

    state = flow.confirm()

    assert identity_calls == [True]
    assert state == {
        "type": "error",
        "data": {
            "message": "Missing operator_id. Execution stopped.",
            "recoverable": True,
        },
    }


def test_axis_failure_renders_error_state():
    flow = make_flow(axis_executor=lambda **kwargs: ({"ok": False}, False))
    advance_to_preview(flow)

    state = flow.confirm()
    rendered = render_tri_state(state)

    assert state["type"] == "error"
    assert state["data"]["message"] == "AXIS execution failed."
    assert "Tri-System Error" in rendered
    assert "AXIS execution failed." in rendered


def test_axis_rejection_does_not_retry_or_mutate_payload():
    axis_calls = []

    def reject_axis(**kwargs):
        axis_calls.append(dict(kwargs))
        return {"ok": False, "reason": "rejected"}, False

    flow = make_flow(axis_executor=reject_axis)
    advance_to_preview(flow)
    original_payload = dict(flow.axis_payload)

    first = flow.confirm()
    second = flow.confirm()

    assert first["type"] == "error"
    assert first["data"]["detail"] == {"ok": False, "reason": "rejected"}
    assert second == {
        "type": "error",
        "data": {
            "message": "AXIS execution already completed.",
            "recoverable": False,
        },
    }
    assert len(axis_calls) == 1
    assert flow.axis_payload == original_payload


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
    assert "classification" in axis_payload
    assert "distortion_class" not in axis_payload


def test_axis_execution_payload_uses_classification_never_distortion_class():
    axis_calls = []

    flow = make_flow(axis_executor=lambda **kwargs: (axis_calls.append(kwargs) or {"ok": True}, True))
    advance_to_preview(flow)
    flow.confirm()

    assert axis_calls
    assert "classification" in axis_calls[0]
    assert "distortion_class" not in axis_calls[0]


def test_sensitive_user_answers_are_not_persisted_in_sapphire_state():
    sensitive_answer = "SECRET-ANSWER-DO-NOT-PERSIST"
    flow = make_flow(NonPersistingDESFlow())

    flow.start()
    flow.submit_answer(sensitive_answer)

    assert sensitive_answer not in repr(flow.question)
    assert sensitive_answer not in repr(flow.des_result)
    assert sensitive_answer not in repr(flow.axis_payload)


def test_boundary_rendering_contains_no_sensitive_answer_or_rejection_detail():
    sensitive_answer = "SECRET-ANSWER-DO-NOT-TRACE"
    sensitive_rejection = "SECRET-AXIS-DETAIL"
    flow = make_flow(
        NonPersistingDESFlow(),
        axis_executor=lambda **kwargs: ({"ok": False, "debug": sensitive_rejection}, False),
    )

    flow.start()
    flow.submit_answer(sensitive_answer)
    state = flow.confirm()
    rendered = render_tri_state(state)

    assert sensitive_answer not in rendered
    assert sensitive_rejection not in rendered
    assert "AXIS execution failed." in rendered


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
