"""Base class for all TTS providers."""
from abc import ABC, abstractmethod
from typing import Optional


class BaseTTSProvider(ABC):
    """Base interface for text-to-speech providers.

    Providers handle audio generation only. Text processing, playback,
    hooks, and threading are handled by TTSClient.
    """

    # Subclasses override to declare their output format
    audio_content_type: str = 'audio/ogg'

    # Speed range — subclasses override for provider-specific limits
    SPEED_MIN: float = 0.5
    SPEED_MAX: float = 2.5

    @abstractmethod
    def generate(self, text: str, voice: str, speed: float, **kwargs) -> Optional[bytes]:
        """Generate audio bytes from text.

        Args:
            text: Cleaned text ready for synthesis.
            voice: Voice identifier (provider-specific).
            speed: Playback speed multiplier.

        Returns:
            Audio bytes in the provider's native format, or None on failure.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is ready to generate audio."""
        ...
