import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TRIGGER_PREFIX = "AXIS:"
DES_BASE_URL = "http://127.0.0.1:8000"
AXIS_EXECUTE_URL = "https://vanta-app-gilt.vercel.app/api/v2/execute"
AXIS_OPERATOR_ID = "Grim"
STATE_PATH = Path("user/axis_runtime_state.json")
ALLOWED_CLASSIFICATIONS = {
    "narrative",
    "emotional",
    "behavioral",
    "perceptual",
    "continuity",
}
AXIS_PAYLOAD_FIELDS = (
    "trigger",
    "classification",
    "next_action",
    "outcome",
    "reference",
    "stability",
    "impact",
)
AXIS_SUCCESS_FIELDS = (
    "sessionId",
    "outcome",
    "continuity_before",
    "continuity_after",
    "protocol_output",
)
CONFIRM_COMMANDS = {"confirm", "comfirm"}


def _load_state():
    if not STATE_PATH.exists():
        return {}

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _clear_state():
    if STATE_PATH.exists():
        STATE_PATH.unlink()


def _format_question(question):
    q_text = question.get("text") or "DES question received."
    options = question.get("options") or []

    if options:
        opts = "\n".join(f"- {o}" for o in options)
        return f"Tri-System DES Question\n{q_text}\n\nOptions:\n{opts}"

    return f"Tri-System DES Question\n{q_text}"


def _build_axis_payload(preview):
    payload = {
        "trigger": preview.get("trigger"),
        "classification": preview.get("classification"),
        "next_action": preview.get("next_action"),
        "outcome": "reduced",
        "reference": preview.get("reference"),
        "stability": preview.get("stability"),
        "impact": preview.get("impact"),
    }

    if payload["classification"] not in ALLOWED_CLASSIFICATIONS:
        raise ValueError("AXIS preview classification is invalid.")
    if payload["reference"] is not True:
        raise ValueError("AXIS preview reference guard must be true.")

    return {
        field: payload[field]
        for field in AXIS_PAYLOAD_FIELDS
    }


def _format_axis_success(data):
    continuity_before = _format_continuity_value(data.get("continuity_before"))
    continuity_after = _format_continuity_value(data.get("continuity_after"))

    return (
        "AXIS Execution Complete\n\n"
        f"sessionId: {data.get('sessionId')}\n"
        f"outcome: {data.get('outcome')}\n"
        f"continuity_before: {continuity_before}\n"
        f"continuity_after: {continuity_after}\n"
        f"protocol_output: {data.get('protocol_output')}"
    )


def _format_continuity_value(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(round(value))
    return value


def _format_axis_failure(data):
    return (
        "AXIS Execution Rejected\n\n"
        f"status_code: {data.get('status_code')}\n"
        f"error: {data.get('error') or data.get('message') or data.get('response_text') or data}\n"
        f"raw_json: {data.get('raw_json')}"
    )


def _execute_axis_preview(preview):
    payload = _build_axis_payload(preview)
    try:
        response = requests.post(
            AXIS_EXECUTE_URL,
            headers={
                "x-operator-id": AXIS_OPERATOR_ID,
                "content-type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        return _format_axis_failure(
            {
                "status_code": None,
                "error": str(exc),
            }
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {
            "status_code": response.status_code,
            "response_text": response.text,
        }

    if not (200 <= response.status_code < 300) or payload.get("ok") is False:
        payload.setdefault("status_code", response.status_code)
        return _format_axis_failure(payload)

    data = payload.get("data") or {}
    missing_fields = [
        field
        for field in AXIS_SUCCESS_FIELDS
        if data.get(field) is None
    ]
    if missing_fields:
        return _format_axis_failure(
            {
                "status_code": response.status_code,
                "error": f"AXIS response missing fields: {', '.join(missing_fields)}",
                "raw_json": payload,
            }
        )

    return _format_axis_success(data)


def _start_des(raw):
    payload = {
        "user_id": "Grim",
        "session_id": "sapphire-web-axis-runtime",
        "trigger_type": "repeat_pricing_visit"
    }

    res = requests.post(
        f"{DES_BASE_URL}/interaction/start",
        json=payload,
        timeout=10
    )

    res.raise_for_status()

    data = res.json()

    question = data.get("question", {})

    state = {
        "active": True,
        "interaction_id": data.get("interaction_id"),
        "last_question_id": question.get("id", "q1"),
        "original_input": raw
    }

    _save_state(state)

    return _format_question(question)


def _answer_des(answer):
    state = _load_state()

    interaction_id = state.get("interaction_id")
    question_id = state.get("last_question_id", "q1")

    if not interaction_id:
        _clear_state()
        return "AXIS Runtime state missing interaction_id."

    payload = {
        "interaction_id": interaction_id,
        "question_id": question_id,
        "answer": answer
    }

    res = requests.post(
        f"{DES_BASE_URL}/interaction/answer",
        json=payload,
        timeout=10
    )

    res.raise_for_status()

    data = res.json()

    if not data.get("done"):
        question = data.get("question", {})

        state["last_question_id"] = question.get("id", "q2")

        _save_state(state)

        return _format_question(question)

    friction_type = data.get("friction_type")

    classification_map = {
        "information_gap": "perceptual",
        "fit_uncertainty": "behavioral",
        "trust_deficit": "narrative"
    }

    classification = classification_map.get(
        friction_type,
        "continuity"
    )

    next_action_map = {
        "perceptual": "Review the clarified decision information and choose one next step.",
        "behavioral": "Choose the smallest committed action and execute it today.",
        "narrative": "Review the evidence and separate verified claims from assumptions.",
        "continuity": "Review the situation carefully before taking the next step."
    }

    next_action = next_action_map.get(classification)

    preview = {
        "trigger": "des_decision_friction",
        "classification": classification,
        "next_action": next_action,
        "reference": True,
        "stability": 6,
        "impact": 4
    }

    _save_state({
        "active": True,
        "phase": "axis_preview",
        "preview": preview
    })

    return (
        "Tri-System AXIS Preview\n\n"
        f"CLASSIFICATION: {classification}\n"
        f"NEXT ACTION: {next_action}\n\n"
        f"trigger: {preview['trigger']}\n"
        f"classification: {preview['classification']}\n"
        f"next_action: {preview['next_action']}\n"
        f"reference: {preview['reference']}\n"
        f"stability: {preview['stability']}\n"
        f"impact: {preview['impact']}\n\n"
        "[Confirm Execution]\n"
        "[Reject]\n\n"
        "Type: confirm OR reject"
    )


def pre_chat(event):
    text = (event.input or "").strip()

    state = _load_state()

    if not text.upper().startswith(TRIGGER_PREFIX) and not state.get("active"):
        return

    if text.upper().startswith(TRIGGER_PREFIX):
        raw = text[len(TRIGGER_PREFIX):].strip()
    else:
        raw = text

    event.skip_llm = True
    event.ephemeral = False
    event.stop_propagation = True

    try:
        if state.get("phase") == "axis_preview":
            lowered = raw.lower().strip()

            if lowered in CONFIRM_COMMANDS:
                preview = state.get("preview") or {}
                try:
                    event.response = _execute_axis_preview(preview)
                finally:
                    _clear_state()
            elif lowered == "reject":
                _clear_state()
                event.response = "AXIS execution rejected."
            else:
                event.response = "AXIS Preview pending. Type: confirm OR reject"

            return

        if state.get("active"):
            event.response = _answer_des(raw)
        else:
            event.response = _start_des(raw)

    except Exception as e:
        logger.exception("AXIS Runtime failure")
        event.response = f"AXIS Runtime error: {e}"
