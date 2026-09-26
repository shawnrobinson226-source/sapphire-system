"""AXIS /api/v2/execute contract: accepted request fields and the success rule.

Pure definitions, no I/O. The transport (axis_http) verifies the v1 envelope;
this module adds the execute-specific rule on top of it.
"""

from __future__ import annotations

from typing import Any

EXECUTE_ENDPOINT = "/api/v2/execute"

# Only request fields AXIS accepts on POST /api/v2/execute.
AXIS_EXECUTE_FIELDS = frozenset({
    "trigger",
    "classification",
    "next_action",
    "outcome",
    "stability",
    "reference",
    "impact",
})

# Named data fields of a verified execute response. Only sessionId has its
# type verified (by has_execute_session_id); the others are copied as-is.
EXECUTE_DATA_FIELDS = (
    "sessionId",
    "outcome",
    "clarity_rating",
    "steps_completed",
    "continuity_before",
    "continuity_after",
    "protocol_output",
)


def has_execute_session_id(data: Any) -> bool:
    """Execute success rule: a verified execution returns a non-empty data.sessionId."""
    session_id = data.get("sessionId") if isinstance(data, dict) else None
    return isinstance(session_id, str) and bool(session_id.strip())
