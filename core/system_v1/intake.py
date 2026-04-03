from __future__ import annotations

from .constants import VALID_ROUTES, VALID_URGENCIES
from .types import TaskInput
from .utils import clean_whitespace


def validate_input(payload: dict) -> None:
    task = clean_whitespace(str(payload.get("task", "")))
    if not task:
        raise ValueError("task cannot be empty")

    urgency = clean_whitespace(str(payload.get("urgency", "normal"))).lower() or "normal"
    if urgency not in VALID_URGENCIES:
        raise ValueError(f"invalid urgency: {urgency}")

    route_override = payload.get("route_override")
    if route_override is not None:
        route_override = clean_whitespace(str(route_override)).lower()
        if route_override and route_override not in VALID_ROUTES:
            raise ValueError(f"invalid route_override: {route_override}")


def build_input(payload: dict) -> TaskInput:
    validate_input(payload)

    constraints = payload.get("constraints") or []
    if not isinstance(constraints, list):
        raise ValueError("constraints must be a list of strings")

    cleaned_constraints = [
        clean_whitespace(str(item))
        for item in constraints
        if clean_whitespace(str(item))
    ]

    raw_route_override = payload.get("route_override", None)
    cleaned_route_override = None
    if raw_route_override is not None:
        cleaned = clean_whitespace(str(raw_route_override)).lower()
        if cleaned:
            cleaned_route_override = cleaned

    return TaskInput(
        task=clean_whitespace(str(payload.get("task", ""))),
        goal=clean_whitespace(str(payload.get("goal", ""))),
        constraints=cleaned_constraints,
        urgency=clean_whitespace(str(payload.get("urgency", "normal"))).lower() or "normal",
        route_override=cleaned_route_override,
    )
