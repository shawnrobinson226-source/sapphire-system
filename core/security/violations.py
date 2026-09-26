"""Sapphire-only boundary violation logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VIOLATION_LOG_PATH = Path("logs") / "sapphire_boundary_violations.log"


# Fixed field labels that may appear by name in a snapshot. Every other key is
# caller-controlled (and may itself carry a secret), so it is only counted and
# its value shape recorded positionally. Includes the AXIS execute request
# fields and the labels Sapphire's own call sites use.
SAFE_KEY_LABELS = frozenset({
    "trigger",
    "classification",
    "next_action",
    "outcome",
    "stability",
    "reference",
    "impact",
    "operator_id",
    "field",
    "fields",
    "unknown_field_count",
    "payload_type",
    "violation_type",
    "kind",
    "status_code",
    "reason",
    "exception_type",
})


def _payload_snapshot(payload: Any, depth: int = 0) -> Any:
    """Return structure-only payload metadata (no raw values, no caller key names)."""
    if depth > 3:
        return {"type": "truncated", "reason": "max_depth"}
    if payload is None:
        return None
    if isinstance(payload, str):
        return {"type": "str", "length": len(payload)}
    if isinstance(payload, bool):
        return {"type": "bool"}
    if isinstance(payload, int):
        return {"type": "int"}
    if isinstance(payload, float):
        return {"type": "float"}
    if isinstance(payload, dict):
        items = list(payload.items())
        known = [(k, v) for k, v in items if isinstance(k, str) and k in SAFE_KEY_LABELS]
        other = [v for k, v in items if not (isinstance(k, str) and k in SAFE_KEY_LABELS)]
        return {
            "type": "dict",
            "size": len(payload),
            "keys": [k for k, _ in known[:50]],
            "value_shapes": {k: _payload_snapshot(v, depth + 1) for k, v in known[:20]},
            "other_key_count": len(other),
            "other_value_shapes": [_payload_snapshot(v, depth + 1) for v in other[:20]],
        }
    if isinstance(payload, (list, tuple)):
        sample = list(payload)[:20]
        return {
            "type": "list" if isinstance(payload, list) else "tuple",
            "length": len(payload),
            "item_shapes": [_payload_snapshot(v, depth + 1) for v in sample],
        }
    return {"type": type(payload).__name__}


def log_boundary_violation(
    violation_type: str,
    endpoint: str | None = None,
    operator_id: str | None = None,
    payload: Any = None,
    details: dict[str, Any] | None = None,
) -> dict:
    """Write one structured JSONL violation entry to Sapphire's boundary log.

    The operator ID value is never written; only whether a non-empty one was
    supplied.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": "sapphire_boundary",
        "violation_type": violation_type,
        "operator_id_present": isinstance(operator_id, str) and bool(operator_id.strip()),
        "endpoint": endpoint,
        "payload_snapshot": _payload_snapshot(payload),
        "details": _payload_snapshot(details),
    }
    VIOLATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VIOLATION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return entry
