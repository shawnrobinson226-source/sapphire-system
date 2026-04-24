# ui/des_flow.py

from core.des.service import DESFlow


def run_des_flow():
    flow = DESFlow()

    trigger_res = flow.trigger({
        "pricing_page_sessions_last_30d": 2,
        "has_converted": False,
        "current_page": "/pricing",
        "session_id": "demo",
        "cooldown_ok": True,
    })

    if not trigger_res.get("show"):
        print("DES not triggered")
        return

    start = flow.start({
        "user_id": "demo_user",
        "session_id": "demo",
        "trigger_type": "repeat_pricing_visit",
    })

    question = start.get("question")

    while question:
        print("\n", question["text"])
        print("Options:", question.get("options"))

        answer = input("Answer: ")

        res = flow.answer({
            "question_id": question["id"],
            "answer": answer,
        })

        if res.get("done"):
            print("\nFINAL OUTPUT:")
            print(res)
            break

        question = res.get("question")
if __name__ == "__main__":
    run_des_flow()