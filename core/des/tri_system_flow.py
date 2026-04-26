"""Step-driven Sapphire -> DES -> AXIS orchestration."""

from core.des.axis_preview import build_axis_preview
from core.des.client import check_health
from core.des.service import DESFlow
from core.identity.operator import resolve_operator_id
from plugins.axis_integration.axis_tools import _execute_axis


TRI_TRIGGER_PAYLOAD = {
    "pricing_page_sessions_last_30d": 2,
    "has_converted": False,
    "current_page": "/pricing",
    "session_id": "demo",
    "cooldown_ok": True,
}

TRI_START_PAYLOAD = {
    "user_id": "demo_user",
    "session_id": "demo",
    "trigger_type": "repeat_pricing_visit",
}

CONFIRM_PROMPT = "Send this execution payload to AXIS?"


class TriSystemFlow:
    def __init__(
        self,
        *,
        des_flow=None,
        health_check=check_health,
        identity_resolver=resolve_operator_id,
        axis_executor=_execute_axis,
    ):
        self.flow = des_flow or DESFlow()
        self.health_check = health_check
        self.identity_resolver = identity_resolver
        self.axis_executor = axis_executor
        self.question = None
        self.des_result = None
        self.axis_payload = None
        self.axis_executed = False

    def start(self):
        self.cancel()
        health = self.health_check()
        if self._has_error(health):
            return self._error("DES unavailable.", recoverable=True)

        trigger_res = self.flow.trigger(dict(TRI_TRIGGER_PAYLOAD))
        if self._has_error(trigger_res):
            return self._error("DES trigger check failed.", recoverable=True)
        if not trigger_res.get("show"):
            return self._error("DES not triggered.", recoverable=True)

        start_res = self.flow.start(dict(TRI_START_PAYLOAD))
        if self._has_error(start_res):
            return self._error("DES interaction failed to start.", recoverable=True)

        return self._set_question(start_res.get("question"))

    def submit_answer(self, answer):
        if not self.question:
            return self._error("No active DES question.", recoverable=True)

        response = self.flow.answer(
            {
                "question_id": self.question["id"],
                "answer": answer,
            }
        )

        if self._has_error(response):
            return self._error("DES interaction failed.", recoverable=True)

        if response.get("done"):
            self.question = None
            self.des_result = response
            self.axis_payload = build_axis_preview(response)
            self.axis_executed = False
            return self._state("result", response)

        return self._set_question(response.get("question"))

    def axis_preview(self):
        if not self.axis_payload:
            return self._error("AXIS preview is not available.", recoverable=True)
        return self._state("axis_preview", self.axis_payload)

    def confirm_state(self):
        if not self.axis_payload:
            return self._error("AXIS payload is not ready for confirmation.", recoverable=True)
        return self._state(
            "confirm",
            {
                "prompt": CONFIRM_PROMPT,
                "payload": self.axis_payload,
            },
        )

    def confirm(self):
        if not self.axis_payload:
            return self._error("AXIS payload is not ready for execution.", recoverable=True)
        if self.axis_executed:
            return self._error("AXIS execution already completed.", recoverable=False)

        operator_id = self.identity_resolver(prompt=True)
        if not operator_id:
            return self._error("Missing operator_id. Execution stopped.", recoverable=True)

        self.axis_executed = True
        axis_result, ok = self.axis_executor(
            trigger=self.axis_payload["trigger"],
            operator_id=operator_id,
            classification=self.axis_payload["classification"],
            next_action=self.axis_payload["next_action"],
            reference=self.axis_payload["reference"],
            stability=self.axis_payload["stability"],
            impact=self.axis_payload["impact"],
        )
        if not ok:
            return self._error("AXIS execution failed.", recoverable=True, data=axis_result)
        return self._state("axis_result", axis_result)

    def cancel(self):
        self.question = None
        self.des_result = None
        self.axis_payload = None
        self.axis_executed = False
        return self._state("idle", {})

    def _set_question(self, question):
        if not self._valid_question(question):
            return self._error("DES returned an invalid question.", recoverable=True)
        self.question = question
        return self._state(
            "question",
            {
                "id": question["id"],
                "text": question["text"],
                "options": list(question.get("options", [])),
            },
        )

    @staticmethod
    def _valid_question(question):
        return (
            isinstance(question, dict)
            and isinstance(question.get("id"), str)
            and bool(question.get("id").strip())
            and isinstance(question.get("text"), str)
            and bool(question.get("text").strip())
            and isinstance(question.get("options", []), list)
        )

    @staticmethod
    def _has_error(response):
        return not isinstance(response, dict) or "error" in response

    @staticmethod
    def _state(state_type, data):
        return {
            "type": state_type,
            "data": data,
        }

    @classmethod
    def _error(cls, message, *, recoverable, data=None):
        error_data = {
            "message": message,
            "recoverable": recoverable,
        }
        if data is not None:
            error_data["detail"] = data
        return cls._state("error", error_data)
