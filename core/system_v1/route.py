from __future__ import annotations

from .constants import TASK_TYPE_TO_ROUTE, VALID_ROUTES


def resolve_route(task_type: str, override: str | None = None) -> str:
    if override:
        if override not in VALID_ROUTES:
            raise ValueError(f"invalid route override: {override}")
        return override

    return TASK_TYPE_TO_ROUTE.get(task_type, "operator")
