"""Sapphire-only boundary violation logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VIOLATION_LOG_PATH = Path("logs") / "sapphire_boundary_violations.log"


def _sanitize_payload(payload: Any) -> Any:
    """Keep payload logging safe and bounded."""
    if payload is None:
        return None
    if isinstance(payload, (str, int, float, bool)):
        return payload
    if isinstance(payload, dict):
        return {str(k): _sanitize_payload(v) for k, v in list(payload.items())[:50]}
    if isinstance(payload, (list, tuple)):
        return [_sanitize_payload(v) for v in list(payload)[:50]]
    return str(payload)


def log_boundary_violation(reason: str, endpoint: str, payload: Any = None) -> dict:
    """Write one structured JSONL violation entry to Sapphire's boundary log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "endpoint": endpoint,
        "payload": _sanitize_payload(payload),
    }
    VIOLATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VIOLATION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return entry

