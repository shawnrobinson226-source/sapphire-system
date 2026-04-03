"""TTS voice validation helpers — single source of truth for voice/provider matching."""
import config


def is_elevenlabs_voice(voice: str) -> bool:
    """Check if a voice string looks like an ElevenLabs voice ID (20+ alphanumeric)."""
    return bool(voice) and len(voice) >= 20 and voice.isalnum()


def default_voice(provider: str = None) -> str:
    """Return the default voice for a TTS provider."""
    if provider is None:
        provider = getattr(config, 'TTS_PROVIDER', 'none')
    if provider == 'kokoro':
        return 'af_heart'
    if provider == 'elevenlabs':
        return getattr(config, 'TTS_ELEVENLABS_VOICE_ID', '') or '21m00Tcm4TlvDq8ikWAM'
    return ''


def validate_voice(voice: str, provider: str = None) -> str:
    """Detect voice/provider mismatch and substitute the correct default.

    An ElevenLabs voice ID on Kokoro (or vice versa) gets swapped for the
    provider's default. Passthrough if voice already matches provider.
    """
    if not voice:
        return voice
    if provider is None:
        provider = getattr(config, 'TTS_PROVIDER', 'none')
    if provider == 'kokoro' and is_elevenlabs_voice(voice):
        return default_voice('kokoro')
    if provider == 'elevenlabs' and not is_elevenlabs_voice(voice):
        return default_voice('elevenlabs')
    return voice
