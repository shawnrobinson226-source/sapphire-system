"""Lightweight Sapphire CLI entry for AXIS-aligned execution service."""

from __future__ import annotations

import argparse
import json
import os

from core.sapphire.axis_adapter import AxisAdapter
from core.sapphire.execution_service import ExecutionService
from core.sapphire.renderer import render_failure, render_gated, render_success


def main() -> int:
    parser = argparse.ArgumentParser(description="Sapphire execution surface CLI")
    parser.add_argument("trigger", help="User trigger text")
    parser.add_argument("--operator-id", required=True, help="Operator identifier")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print raw structured response")
    parser.add_argument(
        "--axis-base-url",
        default=os.environ.get("AXIS_BASE_URL", "http://localhost:3000"),
        help="AXIS base URL",
    )
    args = parser.parse_args()

    adapter = AxisAdapter(axis_base_url=args.axis_base_url)
    service = ExecutionService(axis_adapter=adapter)
    result = service.execute(args.trigger, operator_id=args.operator_id)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=True))
    else:
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
