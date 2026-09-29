"""Lightweight Sapphire CLI for local session history.

S5: direct AXIS execution was removed from this CLI. Execution reaches AXIS
only through the governed tri flow (DES decision, preview, operator confirm).
This entry point creates sessions and displays stored session timelines.
"""

from __future__ import annotations

import argparse
import json

from core.sapphire.renderer import render_failure, render_gated, render_success
from core.sapphire.session_service import SessionService
from core.sapphire.session_store import SessionStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Sapphire session history CLI")
    parser.add_argument("--operator-id", required=False, help="Operator identifier")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print raw structured response")
    parser.add_argument("--new-session", action="store_true", help="Create a new session and print its session_id")
    parser.add_argument("--show-session", dest="show_session_id", help="Show stored session timeline")
    args = parser.parse_args()

    session_store = SessionStore()
    session_service = SessionService(session_store=session_store)

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
                # Legacy entry: its stored message is never re-displayed.
                output = render_gated({"gated": True})
            elif result_type == "success":
                output = render_success({"ok": True, "axis": entry.get("axis", {})})
            else:
                failure = entry.get("failure") or {}
                # The stored message is never displayed; render_failure uses
                # fixed text and only allowlisted kind / valid status.
                output = render_failure(
                    {
                        "ok": False,
                        "error_type": failure.get("error_type"),
                        "safe_details": failure.get("safe_details"),
                    }
                )
            print(output)
        return 0

    parser.print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
