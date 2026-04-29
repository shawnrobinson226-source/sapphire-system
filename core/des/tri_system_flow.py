"""Step-driven Sapphire -> DES -> AXIS orchestration."""

import time

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
PENDING_EXECUTION_TTL_SECONDS = 30 * 60
TRACE_STEPS = {
    "DES_REQUESTED",
    "DES_RETURNED",
    "AXIS_PREVIEW_SHOWN",
    "USER_CONFIRMED",
    "USER_CANCELLED",
    "AXIS_EXECUTED",
    "AXIS_REJECTED",
}
TRACE_STATUSES = {"ok", "fail"}


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
        self.pending_execution = None
        self.axis_executed = False
        self.trace = []
        self.preview_traced = False
        self.gate_events = []

    def start(self):
        self._reset_state()
        self.trace = []
        self._trace("DES_REQUESTED", "ok")
        health = self.health_check()
        if self._has_error(health):
            self._trace("DES_RETURNED", "fail")
            return self._error("DES unavailable.", recoverable=True)

        trigger_res = self.flow.trigger(dict(TRI_TRIGGER_PAYLOAD))
        if self._has_error(trigger_res):
            self._trace("DES_RETURNED", "fail")
            return self._error("DES trigger check failed.", recoverable=True)
        if not trigger_res.get("show"):
            self._trace("DES_RETURNED", "fail")
            return self._error("DES not triggered.", recoverable=True)

        start_res = self.flow.start(dict(TRI_START_PAYLOAD))
        if self._has_error(start_res):
            self._trace("DES_RETURNED", "fail")
            return self._error("DES interaction failed to start.", recoverable=True)

        question_state = self._set_question(start_res.get("question"))
        if question_state.get("type") == "error":
            self._trace("DES_RETURNED", "fail")
        return question_state

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
            self._trace("DES_RETURNED", "fail")
            return self._error("DES interaction failed.", recoverable=True)

        if response.get("done"):
            self.question = None
            self.des_result = response
            self.axis_payload = build_axis_preview(response)
            self._create_pending_execution(self.axis_payload)
            self.axis_executed = False
            self.preview_traced = False
            self._trace("DES_RETURNED", "ok")
            return self._state("result", response)

        question_state = self._set_question(response.get("question"))
        if question_state.get("type") == "error":
            self._trace("DES_RETURNED", "fail")
        return question_state

    def axis_preview(self):
        pending = self._valid_pending_execution()
        if not pending:
            return self._error("AXIS preview is not available.", recoverable=True)
        if not self.preview_traced:
            self._trace("AXIS_PREVIEW_SHOWN", "ok")
            self.preview_traced = True
        return self._state("axis_preview", pending["payload"])

    def confirm_state(self):
        pending = self._valid_pending_execution()
        if not pending:
            return self._error("AXIS payload is not ready for confirmation.", recoverable=True)
        return self._state(
            "confirm",
            {
                "prompt": "Proposed Action",
                "payload": pending["payload"],
            },
        )

    def confirm(self):
        pending = self._valid_pending_execution()
        if not pending:
            return self._error("AXIS payload is not ready for execution.", recoverable=True)
        if self.axis_executed:
            return self._error("AXIS execution already completed.", recoverable=False)

        self._trace("USER_CONFIRMED", "ok")
        operator_id = self.identity_resolver(prompt=True)
        if not operator_id:
            self._clear_pending_execution()
            return self._error("Missing operator_id. Execution stopped.", recoverable=True)

        pending["operator_id"] = operator_id
        self.axis_executed = True
        payload = pending["payload"]
        self._log_gate_event("confirmed", payload)
        try:
            axis_result, ok = self.axis_executor(
                trigger=payload["trigger"],
                operator_id=operator_id,
                classification=payload["classification"],
                next_action=payload["next_action"],
                reference=payload["reference"],
                stability=payload["stability"],
                impact=payload["impact"],
            )
            if not ok:
                self._trace("AXIS_REJECTED", "fail")
                return self._error("AXIS execution failed.", recoverable=True, data=axis_result)
            self._trace("AXIS_EXECUTED", "ok")
            return self._state("axis_result", axis_result)
        finally:
            self._clear_pending_execution()

    def cancel(self):
        pending = self.pending_execution
        if pending:
            self._trace("USER_CANCELLED", "ok")
            self._log_gate_event("rejected", pending.get("payload") or {})
        self._reset_state()
        return self._state("idle", {})

    def get_trace(self):
        return [dict(event) for event in self.trace]

    def _reset_state(self):
        self.question = None
        self.des_result = None
        self.axis_payload = None
        self.pending_execution = None
        self.axis_executed = False
        self.preview_traced = False

    def _create_pending_execution(self, payload):
        now = time.time()
        # Pending execution state must never trigger AXIS by itself.
        self.pending_execution = {
            "payload": dict(payload),
            "operator_id": "",
            "created_at": now,
            "expires_at": now + PENDING_EXECUTION_TTL_SECONDS,
            "status": "pending",
        }

    def _valid_pending_execution(self):
        pending = self.pending_execution
        if not pending:
            return None
        if pending.get("expires_at", 0) <= time.time():
            self._log_gate_event("expired", pending.get("payload") or {})
            self._clear_pending_execution()
            return None
        if pending.get("status") != "pending":
            self._clear_pending_execution()
            return None
        return pending

    def _clear_pending_execution(self):
        self.pending_execution = None
        self.axis_payload = None

    def _log_gate_event(self, action, payload):
        self.gate_events.append(
            {
                "action": action,
                "classification": payload.get("classification", ""),
                "timestamp": time.time(),
            }
        )

    def get_gate_events(self):
        return [dict(event) for event in self.gate_events]

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

    def _trace(self, step, status):
        if step not in TRACE_STEPS or status not in TRACE_STATUSES:
            return
        self.trace.append(
            {
                "timestamp": time.time(),
                "step": step,
                "status": status,
            }
        )

    @classmethod
    def _error(cls, message, *, recoverable, data=None):
        error_data = {
            "message": message,
            "recoverable": recoverable,
        }
        if data is not None:
            error_data["detail"] = data
        return cls._state("error", error_data)
