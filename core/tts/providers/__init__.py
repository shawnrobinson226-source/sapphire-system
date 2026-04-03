"""TTS provider factory."""
import logging

from .base import BaseTTSProvider

logger = logging.getLogger(__name__)


def get_tts_provider(provider_name: str) -> BaseTTSProvider:
    """Create a TTS provider instance by name.

    Supported: 'kokoro', 'elevenlabs', 'none'/empty.
    """
    if not provider_name or provider_name == 'none':
        from .null import NullTTSProvider
        return NullTTSProvider()

    if provider_name == 'kokoro':
        from .kokoro import KokoroTTSProvider
        return KokoroTTSProvider()

    if provider_name == 'elevenlabs':
        from .elevenlabs import ElevenLabsTTSProvider
        return ElevenLabsTTSProvider()

    if provider_name == 'sapphire_router':
        from .sapphire_router import SapphireRouterTTSProvider
        return SapphireRouterTTSProvider()

    logger.warning(f"Unknown TTS provider '{provider_name}', falling back to null")
    from .null import NullTTSProvider
    return NullTTSProvider()
