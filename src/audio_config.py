from __future__ import annotations

from dataclasses import dataclass


DEFAULT_CHUNK_SECONDS = 20
DEFAULT_CHUNK_OVERLAP_SECONDS = 2
DEFAULT_MIN_CHUNK_SECONDS = 10
DEFAULT_MAX_CHUNK_SECONDS = 24
DEFAULT_SILENCE_DURATION_SECONDS = 0.35
DEFAULT_SILENCE_NOISE_LEVEL = "-35dB"
SHORTFORM_LIMIT_SECONDS = 24.5
MAX_WORD_OVERLAP = 12
MAX_SENTENCE_OVERLAP = 2


@dataclass
class AudioProcessingConfig:
    chunk_seconds: int = DEFAULT_CHUNK_SECONDS
    overlap_seconds: int = DEFAULT_CHUNK_OVERLAP_SECONDS
    min_chunk_seconds: int = DEFAULT_MIN_CHUNK_SECONDS
    max_chunk_seconds: int = DEFAULT_MAX_CHUNK_SECONDS
    silence_duration_seconds: float = DEFAULT_SILENCE_DURATION_SECONDS
    silence_noise_level: str = DEFAULT_SILENCE_NOISE_LEVEL


