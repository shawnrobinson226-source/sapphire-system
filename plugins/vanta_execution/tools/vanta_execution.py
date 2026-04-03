"""
VANTA Execution plugin - System V1 interface for Sapphire
"""

import logging

from core.system_v1.service import (
    create_task_plan,
    update_step_status,
    get_recent_tasks,
    start_task,
    block_task,
    complete_task,
)

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = "\u2699"
AVAILABLE_FUNCTIONS = [
    "create_task_plan",
    "update_step_status",
    "get_recent_tasks",
    "start_task",
    "block_task",
    "complete_task",
]

TOOLS = [
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "create_task_plan",
            "description": "Create a structured task with route, steps, and next action.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Raw task description"},
                    "goal": {"type": "string", "description": "Optional goal"},
                    "constraints": {"type": "array", "items": {"type": "string"}, "description": "Optional constraints"},
                    "urgency": {"type": "string", "description": "low, normal, or high"},
                    "route_override": {"type": "string", "description": "builder, researcher, operator, or editor"}
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "update_step_status",
            "description": "Update the status of one step in a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "step_id": {"type": "string"},
                    "new_status": {"type": "string", "description": "pending, active, complete, or blocked"},
                    "note": {"type": "string"}
                },
                "required": ["task_id", "step_id", "new_status"]
            }
        }
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "get_recent_tasks",
            "description": "Return recent task objects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max tasks to return"}
                }
            }
        }
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "start_task",
            "description": "Set a task state to active.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "note": {"type": "string"}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "block_task",
            "description": "Mark a task as blocked with an optional reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "note": {"type": "string"}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "is_local": True,
        "function": {
            "name": "complete_task",
            "description": "Mark a task and all its steps as complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "note": {"type": "string"}
                },
                "required": ["task_id"]
            }
        }
    }
]


def execute(function_name, arguments, config):
    try:
        arguments = arguments or {}

        if function_name == "create_task_plan":
            return create_task_plan(
                task=arguments.get("task", ""),
                goal=arguments.get("goal", ""),
                constraints=arguments.get("constraints"),
                urgency=arguments.get("urgency", "normal"),
                route_override=arguments.get("route_override"),
            ), True

        if function_name == "update_step_status":
            return update_step_status(
                task_id=arguments.get("task_id", ""),
                step_id=arguments.get("step_id", ""),
                new_status=arguments.get("new_status", ""),
                note=arguments.get("note", ""),
            ), True

        if function_name == "get_recent_tasks":
            return get_recent_tasks(limit=arguments.get("limit", 5)), True

        if function_name == "start_task":
            return start_task(
                task_id=arguments.get("task_id", ""),
                note=arguments.get("note", ""),
            ), True

        if function_name == "block_task":
            return block_task(
                task_id=arguments.get("task_id", ""),
                note=arguments.get("note", ""),
            ), True

        if function_name == "complete_task":
            return complete_task(
                task_id=arguments.get("task_id", ""),
                note=arguments.get("note", ""),
            ), True

        return f"Unknown function '{function_name}'.", False

    except Exception as e:
        logger.error("VANTA execution plugin error: %s", e, exc_info=True)
        return f"Error: {e}", False