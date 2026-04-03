"""STT Provider factory."""
import logging
from core.stt.providers.base import BaseSTTProvider

logger = logging.getLogger(__name__)


def get_stt_provider(provider_name: str) -> BaseSTTProvider:
    """Create an STT provider instance by name.

    Args:
        provider_name: 'none', 'faster_whisper', or 'fireworks_whisper'
    """
    if not provider_name or provider_name == 'none':
        from core.stt.stt_null import NullWhisperClient
        return NullWhisperClient()

    if provider_name == 'faster_whisper':
        from core.stt.providers.faster_whisper import FasterWhisperProvider
        return FasterWhisperProvider()

    if provider_name == 'fireworks_whisper':
        from core.stt.providers.fireworks_whisper import FireworksWhisperProvider
        return FireworksWhisperProvider()

    if provider_name == 'sapphire_router':
        from core.stt.providers.sapphire_router import SapphireRouterSTTProvider
        return SapphireRouterSTTProvider()

    logger.error(f"Unknown STT provider: {provider_name}, falling back to null")
    from core.stt.stt_null import NullWhisperClient
    return NullWhisperClient()
