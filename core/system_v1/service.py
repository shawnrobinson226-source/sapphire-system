from __future__ import annotations

import json
from pathlib import Path

from .engine import create_task_object
from .utils import utc_timestamp

DATA_FILE = Path("./data/system_v1_tasks.jsonl")


def _ensure_file():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("", encoding="utf-8")


def _read_all():
    _ensure_file()
    lines = DATA_FILE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _write_all(tasks):
    DATA_FILE.write_text(
        "\n".join(json.dumps(task) for task in tasks),
        encoding="utf-8",
    )


def _find_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def _derive_task_state_from_steps(steps):
    statuses = [step.get("status", "pending") for step in steps]
    if statuses and all(status == "complete" for status in statuses):
        return "complete"
    if any(status == "active" for status in statuses):
        return "active"
    if any(status == "blocked" for status in statuses) and not any(status == "active" for status in statuses):
        return "blocked"
    return "pending"


def _next_action_from_steps(steps):
    for step in steps:
        if step.get("status") == "pending":
            return step.get("label", "Continue task")
    return "Task complete"


def create_task_plan(
    task: str,
    goal: str = "",
    constraints: list[str] | None = None,
    urgency: str = "normal",
    route_override: str | None = None,
) -> dict:
    task_obj = create_task_object({
        "task": task,
        "goal": goal,
        "constraints": constraints or [],
        "urgency": urgency,
        "route_override": route_override,
    })
    task_dict = task_obj.to_dict()
    tasks = _read_all()
    tasks.append(task_dict)
    _write_all(tasks)
    return task_dict


def update_task_state(task_id: str, new_state: str, note: str = "") -> dict:
    tasks = _read_all()
    task = _find_task(tasks, task_id)
    if not task:
        return {"error": "Task not found"}
    task["state"] = new_state
    task["updated_at"] = utc_timestamp()
    if note:
        task.setdefault("notes", []).append(note)
    _write_all(tasks)
    return task


def update_step_status(task_id: str, step_id: str, new_status: str, note: str = "") -> dict:
    tasks = _read_all()
    task = _find_task(tasks, task_id)
    if not task:
        return {"error": "Task not found"}
    matched = False
    for step in task.get("steps", []):
        if step.get("id") == step_id:
            step["status"] = new_status
            matched = True
            break
    if not matched:
        return {"error": "Step not found"}
    task["state"] = _derive_task_state_from_steps(task.get("steps", []))
    task["next_action"] = _next_action_from_steps(task.get("steps", []))
    task["updated_at"] = utc_timestamp()
    if note:
        task.setdefault("notes", []).append(note)
    _write_all(tasks)
    return task


def get_recent_tasks(limit: int = 5) -> list[dict]:
    tasks = _read_all()
    tasks = sorted(tasks, key=lambda t: t.get("updated_at", ""), reverse=True)
    return tasks[:limit]


def get_task(task_id: str) -> dict | None:
    tasks = _read_all()
    return _find_task(tasks, task_id)


def start_task(task_id: str, note: str = "") -> dict:
    tasks = _read_all()
    task = _find_task(tasks, task_id)
    if not task:
        return {"error": "Task not found"}
    task["state"] = "active"
    task["updated_at"] = utc_timestamp()
    if note:
        task.setdefault("notes", []).append(note)
    _write_all(tasks)
    return task


def block_task(task_id: str, note: str = "") -> dict:
    tasks = _read_all()
    task = _find_task(tasks, task_id)
    if not task:
        return {"error": "Task not found"}
    task["state"] = "blocked"
    task["updated_at"] = utc_timestamp()
    if note:
        task.setdefault("notes", []).append(note)
    _write_all(tasks)
    return task


def complete_task(task_id: str, note: str = "") -> dict:
    tasks = _read_all()
    task = _find_task(tasks, task_id)
    if not task:
        return {"error": "Task not found"}
    for step in task.get("steps", []):
        step["status"] = "complete"
    task["state"] = "complete"
    task["next_action"] = "Task complete"
    task["updated_at"] = utc_timestamp()
    if note:
        task.setdefault("notes", []).append(note)
    _write_all(tasks)
    return task