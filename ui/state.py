"""UI state model for Sapphire minimal execution surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UIState:
    operator_id: str = ""
    session_id: str = ""
    latest_response: dict[str, Any] | None = None
    session_history: list[dict[str, Any]] = field(default_factory=list)
    loading: bool = False
    safe_error: str = ""
