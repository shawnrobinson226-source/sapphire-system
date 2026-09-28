"""AXIS /api/v2/execute contract: accepted request fields, the success rule,
and the display-safe failure vocabulary.

Pure definitions, no I/O. The transport (axis_http) verifies the v1 envelope;
this module adds the execute-specific rule on top of it. axis_http imports
this module, so the failure kinds below are spelled as literals rather than
imported from axis_http; a test pins them to the axis_http constants.
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


# Controlled failure kinds a caller may display or store: the axis_http
# transport kinds (minus success / not_configured) plus the execute rule's
# missing_session_id. Anything else is untrusted and is never echoed.
KIND_MISSING_SESSION_ID = "missing_session_id"

REMOTE_FAILURE_KINDS = frozenset({
    "redirect",
    "http_error",
    "timeout",
    "connection_error",
    "non_json",
    "not_ok",
    "auth_not_configured",
    "bypass_invalid",
    "insecure_transport",
    KIND_MISSING_SESSION_ID,
})


def safe_status(value: Any) -> int | None:
    """Return an HTTP status only when it is an int in 100-599."""
    if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
        return value
    return None
