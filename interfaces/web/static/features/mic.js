// features/mic.js - Mic button state, TTS detection, recording handlers
import * as audio from '../audio.js';
import { getElements } from '../core/state.js';
import { handleSend } from '../handlers/send-handlers.js';

let micIconPollInterval = null;

function fillPromptInput(text) {
    const { input } = getElements();
    if (!input) return;
    input.value = text || '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
}

function setMicState(state, message = '') {
    const { micBtn } = getElements();
    if (!micBtn) return;
    micBtn.dataset.micState = state;
    micBtn.dataset.micMessage = message;
    if (state === 'listening') {
        micBtn.classList.add('recording');
        micBtn.title = 'Listening...';
    } else {
        micBtn.classList.remove('recording');
        if (message) micBtn.title = message;
    }
}

export function updateMicButtonState() {
    const { micBtn } = getElements();
    if (!micBtn) return;

    if (micBtn.dataset.micState === 'error' && micBtn.dataset.micMessage) {
        micBtn.textContent = '🎤';
        micBtn.title = micBtn.dataset.micMessage;
        return;
    }

    // Check both browser TTS and local (server speaker) TTS
    const ttsActive = audio.isTtsPlaying() || audio.isLocalTtsPlaying();

    if (ttsActive) {
        micBtn.classList.add('tts-playing');
        micBtn.textContent = '⏹';
        micBtn.title = 'Stop TTS';
    } else {
        micBtn.classList.remove('tts-playing');
        micBtn.textContent = '🎤';
        micBtn.title = micBtn.dataset.sttTitle || 'Use microphone';
    }
}

export function startMicIconPolling() {
    if (micIconPollInterval) return;
    micIconPollInterval = setInterval(updateMicButtonState, 200);
    // Also start local TTS status polling
    audio.startLocalTtsPoll();
}

export function stopMicIconPolling() {
    if (micIconPollInterval) {
        clearInterval(micIconPollInterval);
        micIconPollInterval = null;
    }
    audio.stopLocalTtsPoll();
}

export async function handleMicPress() {
    // If any TTS is playing (browser or local), stop it instead of recording
    if (audio.isTtsPlaying() || audio.isLocalTtsPlaying()) {
        audio.stop(true);
        updateMicButtonState();
        return;
    }

    const { micBtn } = getElements();
    if (audio.getRecState()) {
        await finishRecording(micBtn);
        return;
    }

    await audio.handlePress(micBtn);
    if (audio.getRecState()) {
        setMicState('listening');
    }
}

async function finishRecording(micBtn) {
    await audio.handleRelease(micBtn, async text => {
        fillPromptInput(text);
        await handleSend();
    });
    setMicState('idle');
    updateMicButtonState();
}

export async function handleMicRelease() {
    // Click-to-toggle: release does not stop recording.
    updateMicButtonState();
}

export function handleMicLeave() {
    updateMicButtonState();
}

export function handleVisibilityChange() {
    // Local STT recording is stopped by mic release.
}
