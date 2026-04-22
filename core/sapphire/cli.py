"""Lightweight Sapphire CLI entry for AXIS-aligned execution service."""

from __future__ import annotations

import argparse
import json
import os

from core.sapphire.axis_adapter import AxisAdapter
from core.sapphire.execution_service import ExecutionService
from core.sapphire.renderer import render_failure, render_gated, render_success
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Sapphire execution surface CLI")
    parser.add_argument("trigger", nargs="?", help="User trigger text")
    parser.add_argument("--operator-id", required=False, help="Operator identifier")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print raw structured response")
    parser.add_argument("--new-session", action="store_true", help="Create a new session and print its session_id")
    parser.add_argument("--session", dest="session_id", help="Execute within an existing session")
    parser.add_argument("--show-session", dest="show_session_id", help="Show stored session timeline")
    parser.add_argument(
        "--axis-base-url",
        default=os.environ.get("AXIS_BASE_URL", "http://localhost:3000"),
        help="AXIS base URL",
    )
    args = parser.parse_args()

    adapter = AxisAdapter(axis_base_url=args.axis_base_url)
    session_store = SessionStore()
    session_service = SessionService(session_store=session_store)
    service = ExecutionService(axis_adapter=adapter, session_service=session_service)

    if args.new_session:
        if not args.operator_id:
            print(render_failure({"error_type": "validation_error", "message": "operator_id is required."}))
            return 1
        session = session_service.create_session(args.operator_id)
        if args.as_json:
            print(json.dumps(session, ensure_ascii=True))
        else:
            print(session["session_id"])
        return 0

    if args.show_session_id:
        session = session_service.get_session(args.show_session_id)
        if args.as_json:
            print(json.dumps(session if session is not None else {}, ensure_ascii=True))
            return 0
        if not session:
            print(render_failure({"error_type": "validation_error", "message": "session not found."}))
            return 1
        for entry in session.get("entries", []):
            timestamp = entry.get("timestamp", "")
            print(f"--- Entry [{timestamp}] ---")
            result_type = entry.get("result_type")
            if result_type == "gated":
                output = render_gated(
                    {
                        "gated": True,
                        "message": (entry.get("gated") or {}).get("message", ""),
                        "gate_type": (entry.get("gated") or {}).get("gate_type"),
                    }
                )
            elif result_type == "success":
                output = render_success({"ok": True, "axis": entry.get("axis", {})})
            else:
                failure = entry.get("failure") or {}
                output = render_failure(
                    {
                        "ok": False,
                        "error_type": failure.get("error_type"),
                        "message": failure.get("message"),
                    }
                )
            print(output)
        return 0

    if not args.operator_id:
        print(render_failure({"error_type": "validation_error", "message": "operator_id is required."}))
        return 1
    if not args.trigger:
        print(render_failure({"error_type": "validation_error", "message": "trigger is required."}))
        return 1

    result = service.execute(args.trigger, operator_id=args.operator_id, session_id=args.session_id)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=True))
        return 0

    if result.get("gated"):
        output = render_gated(result)
    elif result.get("ok"):
        output = render_success(result)
    else:
        output = render_failure(result)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
