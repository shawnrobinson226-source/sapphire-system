from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class TaskInput:
    task: str
    goal: str = ""
    constraints: List[str] = field(default_factory=list)
    urgency: str = "normal"
    route_override: Optional[str] = None


@dataclass
class TaskStep:
    id: str
    label: str
    status: str = "pending"


@dataclass
class TaskObject:
    id: str
    task: str
    normalized_task: str
    goal: str
    constraints: List[str]
    urgency: str
    task_type: str
    route: str
    steps: List[TaskStep]
    state: str
    result_summary: str
    next_action: str
    notes: List[str]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)
