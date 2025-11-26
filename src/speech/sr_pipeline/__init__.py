"""
Minimal proof of concept for sr_pipeline three-thread architecture.
"""

__version__ = "0.1.0"

from .pipeline import AudioPipeline
from .energy_vad import EnergyVAD
from .types import AudioChunk, Utterance, PipelineMetrics, VADResult

__all__ = [
    "AudioPipeline",
    "EnergyVAD",
    "AudioChunk",
    "Utterance",
    "PipelineMetrics",
    "VADResult",
]
