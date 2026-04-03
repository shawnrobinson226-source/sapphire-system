from __future__ import annotations

from .constants import CLASSIFY_PATTERNS


def classify_task(normalized_task: str) -> str:
    task = normalized_task.strip()

    for task_type, keywords in CLASSIFY_PATTERNS:
        for keyword in keywords:
            if keyword in task:
                return task_type

    return "general"
