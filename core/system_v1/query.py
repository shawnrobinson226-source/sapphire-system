from __future__ import annotations

from .log_store import load_all_tasks


def get_recent_tasks(limit: int = 5) -> list[dict]:
    tasks = load_all_tasks()
    tasks = sorted(tasks, key=lambda task: task.updated_at, reverse=True)
    return [task.to_dict() for task in tasks[:limit]]


def get_task_by_id(task_id: str) -> dict | None:
    for task in load_all_tasks():
        if task.id == task_id:
            return task.to_dict()
    return None
