from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# New preferred helper
def generate_task_id() -> str:
    return f"tsk_{uuid4().hex[:12]}"


# Backward-compatible alias expected by engine.py
def make_task_id() -> str:
    return generate_task_id()


def generate_step_id(index: int) -> str:
    if index < 1:
        raise ValueError("Step index must be >= 1.")
    return f"step_{index}"


def clean_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


# Backward-compatible alias
def clean_text(value: str) -> str:
    return clean_whitespace(value)


# Backward-compatible helper expected by normalize.py
def normalize_text(value: str) -> str:
    return clean_whitespace(value).lower()


def get_next_pending_step(steps: list[dict]) -> str:
    for step in steps:
        if step.get("status") == "pending":
            return step.get("label", "Continue task")
    return "All steps complete"


def clean_constraints(constraints: list[str] | None) -> list[str]:
    if not constraints:
        return []
    cleaned: list[str] = []
    for item in constraints:
        text = clean_whitespace(str(item))
        if text:
            cleaned.append(text)
    return cleaned