"""STT module — provider-agnostic audio transcription."""

# Always import null by default — real recorder is loaded by switch_stt_provider()
# This prevents startup crashes if audio dependencies aren't installed
from .stt_null import NullAudioRecorder as AudioRecorder

# Re-export factory
from .providers import get_stt_provider

__all__ = ['AudioRecorder', 'get_stt_provider']
