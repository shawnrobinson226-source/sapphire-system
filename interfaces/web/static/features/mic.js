// features/mic.js - Mic button state, TTS detection, recording handlers
import * as audio from '../audio.js';
import * as ui from '../ui.js';
import { getElements, getIsProc, getSttEnabled, getSttReady } from '../core/state.js';

let micIconPollInterval = null;
let browserRecognition = null;
let browserRecognitionActive = false;

function getSpeechRecognition() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function fillPromptInput(text) {
    const { input } = getElements();
    if (!input) return;
    input.value = text || '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
}

function setBrowserMicState(state, message = '') {
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

function startBrowserSpeechRecognition() {
    const SpeechRecognition = getSpeechRecognition();
    if (!SpeechRecognition) {
        const message = 'Speech recognition is unavailable in this browser.';
        setBrowserMicState('error', message);
        ui.showToast(message, 'error');
        return true;
    }

    if (browserRecognitionActive) return true;

    browserRecognition = new SpeechRecognition();
    browserRecognition.interimResults = false;
    browserRecognition.maxAlternatives = 1;

    browserRecognition.addEventListener('result', event => {
        const transcript = event.results?.[0]?.[0]?.transcript || '';
        fillPromptInput(transcript);
    });

    browserRecognition.addEventListener('error', () => {
        const message = 'Microphone input failed.';
        browserRecognitionActive = false;
        setBrowserMicState('error', message);
        ui.showToast(message, 'error');
    });

    browserRecognition.addEventListener('end', () => {
        browserRecognitionActive = false;
        setBrowserMicState('idle');
    });

    browserRecognitionActive = true;
    setBrowserMicState('listening');
    browserRecognition.start();
    return true;
}

export function updateMicButtonState() {
    const { micBtn } = getElements();
    if (!micBtn) return;

    if (browserRecognitionActive) {
        micBtn.textContent = '🎤';
        micBtn.title = 'Listening...';
        return;
    }

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
        const canRecord = getSttEnabled() && getSttReady();
        micBtn.textContent = canRecord ? '🎤' : '🎤';
        micBtn.title = micBtn.dataset.sttTitle || 'Hold to record';
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
    const { micBtn } = getElements();
    
    // If any TTS is playing (browser or local), stop it instead of recording
    if (audio.isTtsPlaying() || audio.isLocalTtsPlaying()) {
        audio.stop(true);
        updateMicButtonState();
        return;
    }

    if (startBrowserSpeechRecognition()) return;
    
    // Block recording if STT is disabled or not initialized
    if (!getSttEnabled() || !getSttReady()) return;

    // Normal recording behavior
    await audio.handlePress(micBtn);
}

export async function handleMicRelease(triggerSendFn) {
    const { micBtn } = getElements();
    if (browserRecognition || browserRecognitionActive) return;
    
    // If TTS was playing (we just stopped it), do nothing on release
    if (micBtn.classList.contains('tts-playing')) {
        updateMicButtonState();
        return;
    }
    
    // Normal recording release
    await audio.handleRelease(micBtn, triggerSendFn);
}

export function handleMicLeave(triggerSendFn) {
    if (browserRecognition || browserRecognitionActive) return;
    if (audio.getRecState()) {
        const { micBtn } = getElements();
        setTimeout(() => {
            if (audio.getRecState()) audio.handleRelease(micBtn, triggerSendFn);
        }, 500);
    }
}

export function handleVisibilityChange(triggerSendFn) {
    if (document.hidden && audio.getRecState()) {
        const { micBtn } = getElements();
        audio.forceStop(micBtn, triggerSendFn);
    }
}
