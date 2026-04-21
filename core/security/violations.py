"""Sapphire-only boundary violation logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VIOLATION_LOG_PATH = Path("logs") / "sapphire_boundary_violations.log"


def _payload_snapshot(payload: Any, depth: int = 0) -> Any:
    """Return structure-only payload metadata (no raw values)."""
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
        keys = [str(k) for k in list(payload.keys())[:50]]
        value_shapes = {str(k): _payload_snapshot(v, depth + 1) for k, v in list(payload.items())[:20]}
        return {
            "type": "dict",
            "size": len(payload),
            "keys": keys,
            "value_shapes": value_shapes,
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
    """Write one structured JSONL violation entry to Sapphire's boundary log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": "sapphire_boundary",
        "violation_type": violation_type,
        "operator_id": operator_id,
        "endpoint": endpoint,
        "payload_snapshot": _payload_snapshot(payload),
        "details": _payload_snapshot(details),
    }
    VIOLATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VIOLATION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return entry
