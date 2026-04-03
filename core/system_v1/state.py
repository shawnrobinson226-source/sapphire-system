from __future__ import annotations

from .constants import VALID_TASK_STATES


def derive_task_state(steps: list, explicit_state: str | None = None) -> str:
    if explicit_state:
        if explicit_state not in VALID_TASK_STATES:
            raise ValueError(f"invalid task state: {explicit_state}")
        return explicit_state

    statuses = [step.status for step in steps]

    if statuses and all(status == "complete" for status in statuses):
        return "complete"

    if any(status == "active" for status in statuses):
        return "active"

    if any(status == "blocked" for status in statuses) and not any(status == "active" for status in statuses):
        return "blocked"

    if statuses and all(status == "pending" for status in statuses):
        return "pending"

    return "pending"
