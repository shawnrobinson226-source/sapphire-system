"""Step-driven Sapphire -> DES -> AXIS orchestration."""

import time

from core.des.axis_preview import build_axis_preview
from core.des.client import check_health
from core.des.service import DESFlow
from core.identity.operator import resolve_operator_id
from core.sapphire import axis_http
from core.sapphire.axis_config import AXIS_NOT_CONFIGURED
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

# Failure kinds the S1/S3 AXIS callers produce. Any other executor "error" value
# is untrusted (it may carry response text, URLs or credentials) and is
# replaced with GENERIC_AXIS_FAILURE.
AXIS_FAILURE_KINDS = frozenset(
    {
        AXIS_NOT_CONFIGURED,
        "missing_session_id",
        axis_http.KIND_REDIRECT,
        axis_http.KIND_HTTP_ERROR,
        axis_http.KIND_TIMEOUT,
        axis_http.KIND_CONNECTION_ERROR,
        axis_http.KIND_NON_JSON,
        axis_http.KIND_NOT_OK,
        axis_http.KIND_AUTH_NOT_CONFIGURED,
        axis_http.KIND_BYPASS_INVALID,
        axis_http.KIND_INSECURE_TRANSPORT,
    }
)
GENERIC_AXIS_FAILURE = "axis_failed"


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
        # axis_attempted: a dispatch was made (single-shot guard).
        # axis_succeeded: AXIS verifiably executed (2xx envelope + data.sessionId).
        self.axis_attempted = False
        self.axis_succeeded = False
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
            self.axis_attempted = False
            self.axis_succeeded = False
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
        if self.axis_attempted:
            return self._error("AXIS execution already attempted.", recoverable=False)

        self._trace("USER_CONFIRMED", "ok")
        operator_id = self.identity_resolver(prompt=True)
        if not operator_id:
            self._clear_pending_execution()
            return self._error("Missing operator_id. Execution stopped.", recoverable=True)

        pending["operator_id"] = operator_id
        self.axis_attempted = True
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
            if not (ok is True and self._is_verified_execution(axis_result)):
                self._trace("AXIS_REJECTED", "fail")
                detail = self._failure_detail(axis_result, ok)
                if detail["error"] == "axis_not_configured":
                    return self._error(
                        "AXIS is not configured. Execution stopped.",
                        recoverable=True,
                        data=detail,
                    )
                return self._error("AXIS execution failed.", recoverable=True, data=detail)
            self.axis_succeeded = True
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
        self.axis_attempted = False
        self.axis_succeeded = False
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
    def _is_verified_execution(axis_result):
        """Execute success rule: validated AXIS data with a non-empty sessionId."""
        session_id = axis_result.get("sessionId") if isinstance(axis_result, dict) else None
        return isinstance(session_id, str) and bool(session_id.strip())

    @staticmethod
    def _failure_detail(axis_result, ok):
        """Allowlisted failure kind and a valid HTTP status only.

        Executor output is untrusted: an unknown "error" value becomes
        GENERIC_AXIS_FAILURE, and status_code is kept only when it is an int
        (not bool) in 100-599. No other executor field is forwarded.
        """
        if ok is True:
            return {"error": "missing_session_id", "status_code": None}
        kind = axis_result.get("error") if isinstance(axis_result, dict) else None
        status = axis_result.get("status_code") if isinstance(axis_result, dict) else None
        if not (isinstance(kind, str) and kind in AXIS_FAILURE_KINDS):
            kind = GENERIC_AXIS_FAILURE
        if not (isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599):
            status = None
        return {"error": kind, "status_code": status}

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
