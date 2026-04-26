from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_browser_mic_targets_main_chat_input_only():
    template = read("interfaces/web/templates/index.html")
    mic_js = read("interfaces/web/static/features/mic.js")

    assert 'id="prompt-input"' in template
    assert 'id="mic-btn"' in template
    assert "window.SpeechRecognition || window.webkitSpeechRecognition" in mic_js
    assert "const { input } = getElements();" in mic_js
    assert "input.value = text || '';" in mic_js
    assert "ui.showToast(message, 'error')" in mic_js
    assert "tri-answer-input" not in mic_js
    assert "tri-mic-button" not in mic_js


def test_transcribed_text_fills_input_without_auto_submit():
    send_handlers = read("interfaces/web/static/handlers/send-handlers.js")
    trigger_fn = send_handlers.split("export async function triggerSendWithText(text)", 1)[1]
    trigger_fn = trigger_fn.split("export function handleInput()", 1)[0]

    assert "input.value = text;" in trigger_fn
    assert "input.dispatchEvent(new Event('input'));" in trigger_fn
    assert "input.focus();" in trigger_fn
    assert "handleSend()" not in trigger_fn


def test_tri_ui_does_not_render_microphone_helper():
    components = read("ui/components.py")

    assert "TriAnswerInput" not in components
    assert "tri-answer-input" not in components
    assert "tri-mic-button" not in components
    assert "SpeechRecognition" not in components
