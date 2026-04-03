from __future__ import annotations

from .breakdown import build_steps
from .classify import classify_task
from .intake import build_input
from .normalize import normalize_task
from .route import resolve_route
from .state import derive_task_state
from .types import TaskObject
from .utils import make_task_id, utc_timestamp


def create_task_object(payload: dict) -> TaskObject:
    task_input = build_input(payload)
    normalized_task = normalize_task(task_input.task)
    task_type = classify_task(normalized_task)
    route = resolve_route(task_type, task_input.route_override)
    steps = build_steps(task_type, route, normalized_task)
    state = derive_task_state(steps)
    now = utc_timestamp()

    pending_step = next((step for step in steps if step.status == "pending"), None)
    next_action = pending_step.label if pending_step else "No pending action."

    return TaskObject(
        id=make_task_id(),
        task=task_input.task,
        normalized_task=normalized_task,
        goal=task_input.goal,
        constraints=task_input.constraints,
        urgency=task_input.urgency,
        task_type=task_type,
        route=route,
        steps=steps,
        state=state,
        result_summary="",
        next_action=next_action,
        notes=[],
        created_at=now,
        updated_at=now,
    )
