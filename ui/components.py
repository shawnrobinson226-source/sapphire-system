"""Minimal UI panel components for Sapphire execution surface."""

from __future__ import annotations

from ui.state import UIState
from ui.views import render_history_entry, render_result, render_tri_state


def SessionControls(state: UIState) -> str:
    return "\n".join(
        [
            "Session",
            f"Operator ID: {state.operator_id or 'N/A'}",
            f"Current Session: {state.session_id or 'N/A'}",
        ]
    )


def TriggerForm(_: UIState) -> str:
    return "\n".join(
        [
            "Submit Trigger",
            "Enter trigger text and submit once.",
        ]
    )


def ResultView(state: UIState) -> str:
    body = render_result(state.latest_response)
    return "Latest Result" if not body else f"Latest Result\n{body}"


def TriSystemView(state: UIState) -> str:
    blocks = [render_tri_state(item) for item in [state.tri_des_result, state.tri_axis_preview, state.tri_state]]
    if state.tri_state and state.tri_state.get("type") == "question":
        blocks.append(TriAnswerInput())
    body = "\n\n".join(block for block in blocks if block)
    return "Tri-System Flow" if not body else body


def TriAnswerInput() -> str:
    return """<div class="tri-answer-input">
  <label for="tri-answer-input">Answer</label>
  <input id="tri-answer-input" name="tri_answer" type="text" autocomplete="off" />
  <button id="tri-mic-button" type="button" aria-label="Use microphone">Mic</button>
  <span id="tri-mic-status" data-state="idle">idle</span>
  <span id="tri-mic-message" role="status"></span>
</div>
<script>
(function () {
  var input = document.getElementById("tri-answer-input");
  var button = document.getElementById("tri-mic-button");
  var status = document.getElementById("tri-mic-status");
  var message = document.getElementById("tri-mic-message");
  if (!input || !button || !status || !message) {
    return;
  }
  var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  function setState(nextState, text) {
    status.dataset.state = nextState;
    status.textContent = nextState;
    message.textContent = text || "";
  }
  if (!SpeechRecognition) {
    setState("error", "Speech recognition is unavailable in this browser.");
    button.disabled = true;
    return;
  }
  var recognition = new SpeechRecognition();
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  button.addEventListener("click", function () {
    setState("listening", "");
    recognition.start();
  });
  recognition.addEventListener("result", function (event) {
    var transcript = event.results[0][0].transcript || "";
    input.value = transcript;
    setState("idle", "");
  });
  recognition.addEventListener("error", function () {
    setState("error", "Microphone input failed.");
  });
  recognition.addEventListener("end", function () {
    if (status.dataset.state === "listening") {
      setState("idle", "");
    }
  });
})();
</script>"""


def HistoryView(state: UIState) -> str:
    if not state.session_history:
        return "Session History"
    blocks = [render_history_entry(entry) for entry in state.session_history]
    return "Session History\n" + "\n".join(blocks)


def AppShell(state: UIState) -> str:
    return "\n\n".join(
        [
            SessionControls(state),
            TriggerForm(state),
            ResultView(state),
            TriSystemView(state),
            HistoryView(state),
        ]
    )
