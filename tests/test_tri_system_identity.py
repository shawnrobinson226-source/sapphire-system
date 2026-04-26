import builtins

import pytest

from core.des import tri_system_flow
from core.des.axis_preview import build_axis_preview
from core.identity import operator


DES_RESULT = {
    "done": True,
    "friction_type": "information_gap",
    "output": {
        "output_type": "clarify",
    },
}


class FakeDESFlow:
    def __init__(self):
        self.trigger_payload = None
        self.start_payload = None
        self.answer_payload = None

    def trigger(self, payload):
        self.trigger_payload = payload
        return {"show": True}

    def start(self, payload):
        self.start_payload = payload
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
        return DES_RESULT


def run_flow(monkeypatch, inputs, flow=None):
    flow = flow or FakeDESFlow()
    tri_flow = tri_system_flow.TriSystemFlow()
    tri_flow.flow = flow

    answers = iter(inputs)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers))
    monkeypatch.setattr(tri_flow, "_des_available", lambda: True)
    tri_flow._run()
    return flow


def test_decline_path_does_not_read_operator_id(monkeypatch):
    def fail_identity(*args, **kwargs):
        raise AssertionError("operator identity should not be read on decline")

    def fail_axis(*args, **kwargs):
        raise AssertionError("AXIS should not execute on decline")

    monkeypatch.setattr(tri_system_flow, "resolve_operator_id", fail_identity)
    monkeypatch.setattr(tri_system_flow, "_execute_axis", fail_axis)

    run_flow(monkeypatch, ["a", "no"])


def test_des_payloads_never_include_operator_id(monkeypatch):
    captured = {}

    def fake_axis(**kwargs):
        captured.update(kwargs)
        return {"ok": True}, True

    monkeypatch.setattr(tri_system_flow, "resolve_operator_id", lambda prompt=False: "operator-1")
    monkeypatch.setattr(tri_system_flow, "_execute_axis", fake_axis)

    fake_flow = run_flow(monkeypatch, ["a", "yes"])

    assert "operator_id" not in fake_flow.trigger_payload
    assert "operator_id" not in fake_flow.start_payload
    assert "operator_id" not in fake_flow.answer_payload
    assert captured["operator_id"] == "operator-1"


def test_missing_env_prompts_only_after_yes(monkeypatch):
    captured = {}

    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(tri_system_flow, "_execute_axis", lambda **kwargs: (captured.update(kwargs) or {"ok": True}, True))

    run_flow(monkeypatch, ["a", "yes", "prompted-operator"])

    assert captured["operator_id"] == "prompted-operator"


def test_valid_env_avoids_prompt(monkeypatch):
    captured = {}

    monkeypatch.setenv(operator.OPERATOR_ID_ENV, " env-operator ")
    monkeypatch.setattr(tri_system_flow, "_execute_axis", lambda **kwargs: (captured.update(kwargs) or {"ok": True}, True))

    run_flow(monkeypatch, ["a", "yes"])

    assert captured["operator_id"] == "env-operator"


def test_invalid_env_prompts_after_yes(monkeypatch):
    captured = {}

    monkeypatch.setenv(operator.OPERATOR_ID_ENV, "   ")
    monkeypatch.setattr(tri_system_flow, "_execute_axis", lambda **kwargs: (captured.update(kwargs) or {"ok": True}, True))

    run_flow(monkeypatch, ["a", "yes", "prompted-operator"])

    assert captured["operator_id"] == "prompted-operator"


def test_axis_payload_preview_does_not_include_operator_id():
    axis_payload = build_axis_preview(DES_RESULT)

    assert "operator_id" not in axis_payload
