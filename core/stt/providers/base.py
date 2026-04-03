"""Base class for all STT providers."""
from abc import ABC, abstractmethod
from typing import Optional


class BaseSTTProvider(ABC):
    """Base interface for speech-to-text providers."""

    @abstractmethod
    def transcribe_file(self, audio_path: str) -> Optional[str]:
        """Transcribe an audio file and return the text."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is ready to transcribe."""
        ...
