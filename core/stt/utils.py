"""Shared STT guard logic."""
import config
from core.stt.stt_null import NullWhisperClient


def can_transcribe(whisper_client) -> tuple[bool, str]:
    """Check if STT transcription is available.

    Returns:
        (ok, reason) - ok=True if transcription can proceed
    """
    provider = getattr(config, 'STT_PROVIDER', 'none')
    if not provider or provider == 'none':
        return False, "Speech-to-text is disabled"
    if isinstance(whisper_client, NullWhisperClient):
        return False, "STT enabled but not initialized — loading speech model"
    if hasattr(whisper_client, 'is_available') and not whisper_client.is_available():
        return False, "STT provider not ready (check API key or model)"
    return True, ""
