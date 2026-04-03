from __future__ import annotations

from .constants import BUILDER_STEPS, RESEARCHER_STEPS, OPERATOR_STEPS, EDITOR_STEPS
from .types import TaskStep


def _tailor_operator_steps(normalized_task: str) -> list[str]:
    task = normalized_task.lower()

    if any(term in task for term in ["install", "set up", "setup", "configure", "initialize"]):
        return [
            "Identify current state",
            "Verify required dependency or condition",
            "Perform the first setup step",
            "Test result",
            "Record blocker or next move",
        ]

    return OPERATOR_STEPS


def build_steps(task_type: str, route: str, normalized_task: str) -> list[TaskStep]:
    if route == "builder":
        labels = BUILDER_STEPS
    elif route == "researcher":
        labels = RESEARCHER_STEPS
    elif route == "editor":
        labels = EDITOR_STEPS
    else:
        labels = _tailor_operator_steps(normalized_task)

    labels = labels[:7]
    if len(labels) < 3:
        raise ValueError("step breakdown must contain 3-7 steps")

    return [TaskStep(id=f"step_{index}", label=label, status="pending") for index, label in enumerate(labels, start=1)]
