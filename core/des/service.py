# core/des/service.py

from core.des.client import (
    check_trigger,
    start_interaction,
    answer_interaction,
)


class DESFlow:
    def __init__(self):
        self.interaction_id = None

    def trigger(self, payload):
        return check_trigger(payload)

    def start(self, payload):
        res = start_interaction(payload)
        self.interaction_id = res.get("interaction_id")
        return res

    def answer(self, answer_payload):
        payload = {
            "interaction_id": self.interaction_id,
            **answer_payload,
        }
        return answer_interaction(payload)