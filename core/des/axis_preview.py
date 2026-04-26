"""Build an operator-visible AXIS execution preview from a DES result."""

AXIS_PAYLOAD_FIELDS = {
    "trigger",
    "classification",
    "next_action",
    "reference",
    "stability",
    "impact",
}

FRICTION_TO_CLASSIFICATION = {
    "information_gap": "perceptual",
    "fit_uncertainty": "behavioral",
    "trust_deficit": "narrative",
    "unknown": "continuity",
}

OUTPUT_TO_NEXT_ACTION = {
    "clarify": "Review the clarified decision information and choose one next step.",
    "filter": "Confirm fit or non-fit and act on the result.",
    "proof": "Review the evidence and separate verified claims from assumptions.",
}


def build_axis_preview(des_result, trigger="des_decision_friction"):
    des_result = des_result or {}
    friction_type = des_result.get("friction_type", "unknown")
    output = des_result.get("output", {}) or {}
    output_type = output.get("output_type", "")

    classification = FRICTION_TO_CLASSIFICATION.get(friction_type, "continuity")
    next_action = OUTPUT_TO_NEXT_ACTION.get(
        output_type,
        "Review the decision output and choose one clear next step.",
    )

    payload = {
        "trigger": trigger,
        "classification": classification,
        "next_action": next_action,
        "reference": True,
        "stability": 6,
        "impact": 4,
    }

    return {
        key: value
        for key, value in payload.items()
        if key in AXIS_PAYLOAD_FIELDS
    }
