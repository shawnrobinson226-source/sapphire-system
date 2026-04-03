"""Null TTS provider — returns nothing."""
import logging
from typing import Optional

from .base import BaseTTSProvider

logger = logging.getLogger(__name__)


class NullTTSProvider(BaseTTSProvider):
    """No-op provider used when TTS is disabled."""

    def generate(self, text: str, voice: str, speed: float, **kwargs) -> Optional[bytes]:
        return None

    def is_available(self) -> bool:
        return False
