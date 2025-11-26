"""Energy-based voice activity detection."""

import numpy as np
from typing import Optional
from .types import AudioChunk, VADResult


class EnergyVAD:
    """
    Simple energy-based voice activity detection.

    Uses RMS (root mean square) energy threshold to detect speech.
    Optionally calibrates threshold based on ambient noise.
    """

    def __init__(self, threshold: float = 300.0, dynamic: bool = True):
        """
        Initialize EnergyVAD.

        Args:
            threshold: RMS energy threshold for speech detection
            dynamic: If True, adapt threshold based on ambient noise
        """
        self.threshold = threshold
        self.dynamic = dynamic
        self._ambient_energy: Optional[float] = None
        self._samples_seen = 0

    def process(self, chunk: AudioChunk) -> VADResult:
        """
        Process an audio chunk and determine if it contains speech.

        Args:
            chunk: Audio data to analyze

        Returns:
            VADResult with speech detection outcome
        """
        # Convert bytes to int16 samples
        samples = np.frombuffer(chunk.data, dtype=np.int16)

        # Calculate RMS energy
        energy = np.sqrt(np.mean(samples.astype(np.float32) ** 2))

        # Dynamic threshold adjustment (simple exponential moving average)
        if self.dynamic and self._samples_seen < 50:  # ~1.5s calibration
            if self._ambient_energy is None:
                self._ambient_energy = energy
            else:
                self._ambient_energy = 0.9 * self._ambient_energy + 0.1 * energy
            self._samples_seen += 1
            effective_threshold = max(self.threshold, self._ambient_energy * 1.5)
        else:
            effective_threshold = self.threshold

        is_speech = energy > effective_threshold
        confidence = min(1.0, energy / effective_threshold) if is_speech else 0.0

        return VADResult(is_speech=is_speech, confidence=confidence)

    def reset(self) -> None:
        """Reset VAD state (no-op for EnergyVAD after calibration)."""
        # Don't reset ambient calibration
        pass
