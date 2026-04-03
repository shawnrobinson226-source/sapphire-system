"""Backwards compat — WhisperSTT now lives in providers.faster_whisper."""
from core.stt.providers.faster_whisper import FasterWhisperProvider as WhisperSTT

__all__ = ['WhisperSTT']
