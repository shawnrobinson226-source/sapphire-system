"""Operator-gated Sapphire -> DES -> AXIS flow."""

from pprint import pprint

from core.des.service import DESFlow
from core.des.client import check_health
from core.des.axis_preview import build_axis_preview
from plugins.axis_integration.axis_tools import _execute_axis


class TriSystemFlow:
    def __init__(self):
        self.flow = DESFlow()

    def run(self):
        try:
            self._run()
        except Exception as error:
            print("Tri-system flow failed closed.")
            print(error)

    def _run(self):
        if not self._des_available():
            print("DES unavailable. Execution stopped.")
            return

        trigger_res = self.flow.trigger({
            "pricing_page_sessions_last_30d": 2,
            "has_converted": False,
            "current_page": "/pricing",
            "session_id": "demo",
            "cooldown_ok": True,
        })

        if "error" in trigger_res:
            print("DES trigger check failed. Execution stopped.")
            pprint(trigger_res)
            return

        if not trigger_res.get("show"):
            print("DES not triggered. Execution stopped.")
            return

        start = self.flow.start({
            "user_id": "demo_user",
            "session_id": "demo",
            "trigger_type": "repeat_pricing_visit",
        })

        if "error" in start:
            print("DES interaction failed to start. Execution stopped.")
            pprint(start)
            return

        question = start.get("question")

        while question:
            print()
            print(question["text"])
            print("Options:", question.get("options"))

            answer = input("Answer: ")

            res = self.flow.answer({
                "question_id": question["id"],
                "answer": answer,
            })

            if "error" in res:
                print("DES interaction failed. Execution stopped.")
                pprint(res)
                return

            if res.get("done"):
                self._preview_and_confirm(res)
                return

            question = res.get("question")

        print("DES interaction ended without a final result. Execution stopped.")

    def _des_available(self):
        health = check_health()
        return "error" not in health

    def _preview_and_confirm(self, des_result):
        axis_payload = build_axis_preview(des_result)

        print("\nFINAL DES OUTPUT:")
        pprint(des_result)

        print("\nAXIS PAYLOAD PREVIEW:")
        pprint(axis_payload)

        confirm = input("\nSend this execution payload to AXIS? ").strip().lower()
        if confirm != "yes":
            print("Execution cancelled. AXIS was not called.")
            return

        operator_id = input("operator_id: ").strip()
        if not operator_id:
            print("Missing operator_id. Execution stopped.")
            return

        axis_result, ok = _execute_axis(
            trigger=axis_payload["trigger"],
            operator_id=operator_id,
            classification=axis_payload["classification"],
            next_action=axis_payload["next_action"],
            reference=axis_payload["reference"],
            stability=axis_payload["stability"],
            impact=axis_payload["impact"],
        )

        print("\nAXIS RESULT:")
        pprint(axis_result)
        if not ok:
            print("AXIS execution failed closed.")
