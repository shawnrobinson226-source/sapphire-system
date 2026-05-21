"""Central AXIS execution guard for Sapphire capability boundaries."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_active_system(explicit_system: Any = None) -> Any:
    if explicit_system is not None:
        return explicit_system
    try:
        from core import api_fastapi

        return getattr(api_fastapi, "_system", None)
    except Exception:
        return None


def _safe_enabled_names(function_manager: Any) -> list[str]:
    if not function_manager:
        return []
    try:
        return function_manager.get_enabled_function_names()
    except Exception:
        try:
            return [
                tool.get("function", {}).get("name")
                for tool in function_manager.enabled_tools
                if tool.get("function", {}).get("name")
            ]
        except Exception:
            return []


def get_capability_snapshot(system: Any = None) -> dict:
    active_system = _get_active_system(system)
    llm_chat = getattr(active_system, "llm_chat", None)
    function_manager = getattr(llm_chat, "function_manager", None)
    session_manager = getattr(llm_chat, "session_manager", None)

    settings = {}
    if session_manager:
        try:
            settings = session_manager.get_chat_settings() or {}
        except Exception:
            logger.exception("[AXIS_GUARD] Failed to read active chat settings")

    current_toolset = getattr(function_manager, "current_toolset_name", None)
    enabled_tools = _safe_enabled_names(function_manager)
    settings_toolset = settings.get("toolset") or settings.get("ability")
    zero_tools_mode = False

    try:
        if function_manager and hasattr(function_manager, "is_zero_tools_mode"):
            zero_tools_mode = function_manager.is_zero_tools_mode()
    except Exception:
        logger.exception("[AXIS_GUARD] Failed to read FunctionManager zero-tools mode")
        zero_tools_mode = True

    if settings_toolset == "none":
        zero_tools_mode = True
    if current_toolset == "none" and not enabled_tools:
        zero_tools_mode = True

    return {
        "has_system": active_system is not None,
        "settings_toolset": settings_toolset,
        "current_toolset": current_toolset,
        "enabled_tools": enabled_tools,
        "zero_tools_mode": zero_tools_mode,
    }


def assert_axis_execution_allowed(path: str, system: Any = None) -> tuple[bool, dict]:
    snapshot = get_capability_snapshot(system)
    logger.warning(
        "[AXIS_GUARD] path=%s settings_toolset=%s current_toolset=%s enabled_tools=%s zero_tools_mode=%s",
        path,
        snapshot.get("settings_toolset"),
        snapshot.get("current_toolset"),
        snapshot.get("enabled_tools"),
        snapshot.get("zero_tools_mode"),
    )
    if snapshot["zero_tools_mode"]:
        return False, {
            "ok": False,
            "status_code": None,
            "error": "AXIS execution blocked because Zero tools mode is active.",
            "path": path,
            "capability_snapshot": snapshot,
        }
    return True, snapshot
