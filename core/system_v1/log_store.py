from __future__ import annotations

import json
from pathlib import Path

from .types import TaskObject, TaskStep


LOG_PATH = Path(__file__).resolve().parent / "data" / "task_log.jsonl"


def _ensure_log_file() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text("", encoding="utf-8")


def append_task(task: TaskObject) -> None:
    _ensure_log_file()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")


def load_all_tasks() -> list[TaskObject]:
    _ensure_log_file()
    tasks: list[TaskObject] = []

    with LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            steps = [TaskStep(**step) for step in raw.get("steps", [])]
            raw["steps"] = steps
            tasks.append(TaskObject(**raw))

    return tasks


def save_rewritten_tasks(tasks: list[TaskObject]) -> None:
    _ensure_log_file()
    with LOG_PATH.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")
