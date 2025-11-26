"""Data types for audio pipeline."""

from dataclasses import dataclass, field
from typing import Optional
import speech_recognition as sr


@dataclass
class AudioChunk:
    """A chunk of audio with metadata."""

    data: bytes
    timestamp: float  # time.monotonic() when captured
    sample_rate: int
    sample_width: int  # bytes per sample (2 for 16-bit)


@dataclass
class Utterance:
    """A complete speech segment ready for transcription."""

    audio: sr.AudioData
    start_time: float
    end_time: float

    @property
    def duration(self) -> float:
        """Return duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class PipelineMetrics:
    """Runtime metrics for monitoring."""

    chunks_captured: int = 0
    chunks_dropped: int = 0
    utterances_detected: int = 0
    utterances_transcribed: int = 0
    transcription_errors: int = 0

    @property
    def drop_rate(self) -> float:
        """Return percentage of dropped chunks."""
        total = self.chunks_captured + self.chunks_dropped
        return self.chunks_dropped / total if total > 0 else 0.0


@dataclass
class VADResult:
    """Result from voice activity detection."""

    is_speech: bool
    confidence: float = 1.0  # 0.0 to 1.0
