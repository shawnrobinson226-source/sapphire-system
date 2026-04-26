"""CLI runner for the step-driven tri-system flow."""

from pprint import pprint

from core.des.tri_system_flow import TriSystemFlow
from ui.views import render_tri_state


def run_tri_system_flow():
    flow = TriSystemFlow()
    state = flow.start()

    while state.get("type") == "question":
        print(render_tri_state(state))
        answer = input("Answer: ")
        state = flow.submit_answer(answer)

    print(render_tri_state(state))

    if state.get("type") != "result":
        return

    preview = flow.axis_preview()
    print(render_tri_state(preview))

    confirm = flow.confirm_state()
    print(render_tri_state(confirm))

    command = input("Confirm or Cancel: ").strip().lower()
    if command != "confirm":
        print(render_tri_state(flow.cancel()))
        return

    result = flow.confirm()
    rendered = render_tri_state(result)
    if rendered:
        print(rendered)
    else:
        pprint(result)


if __name__ == "__main__":
    run_tri_system_flow()
