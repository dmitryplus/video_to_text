from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from src.audio_config import (
    AudioProcessingConfig,
    MAX_SENTENCE_OVERLAP,
    MAX_WORD_OVERLAP,
    SHORTFORM_LIMIT_SECONDS,
)
from src.progress_bar import ProgressBar


class AudioProcessor:
    def __init__(self, config: AudioProcessingConfig):
        self.config = config

    def probe_duration(self, audio_path: Path) -> float:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())

    def export_chunk(
        self, source_path: Path, start_seconds: float, duration_seconds: float, out_path: Path
    ) -> None:
        command = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            str(start_seconds),
            "-t",
            str(duration_seconds),
            "-i",
            str(source_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(out_path),
        ]
        subprocess.run(command, check=True)

    def detect_silence_boundaries(self, audio_path: Path) -> list[float]:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(audio_path),
            "-af",
            (
                "silencedetect="
                f"noise={self.config.silence_noise_level}:"
                f"d={self.config.silence_duration_seconds}"
            ),
            "-f",
            "null",
            "-",
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        boundaries: list[float] = []
        current_start: float | None = None

        for line in result.stderr.splitlines():
            start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
            if start_match:
                current_start = float(start_match.group(1))
                continue

            end_match = re.search(r"silence_end:\s*([0-9.]+)", line)
            if end_match and current_start is not None:
                silence_end = float(end_match.group(1))
                boundaries.append((current_start + silence_end) / 2)
                current_start = None

        return boundaries

    def build_segments(
        self, total_duration: float, silence_boundaries: list[float]
    ) -> list[tuple[float, float]]:
        if total_duration <= self.config.chunk_seconds:
            return [(0.0, total_duration)]

        segments: list[tuple[float, float]] = []
        current_start = 0.0
        min_end_padding = max(0.0, float(self.config.min_chunk_seconds))
        preferred_end_padding = max(min_end_padding, float(self.config.chunk_seconds))
        max_end_padding = max(
            preferred_end_padding,
            min(float(self.config.max_chunk_seconds), SHORTFORM_LIMIT_SECONDS),
        )

        while current_start < total_duration:
            min_end = min(total_duration, current_start + min_end_padding)
            preferred_end = min(total_duration, current_start + preferred_end_padding)
            max_end = min(total_duration, current_start + max_end_padding)

            if max_end >= total_duration:
                segments.append((current_start, total_duration))
                break

            candidates = [
                boundary
                for boundary in silence_boundaries
                if min_end <= boundary <= max_end
            ]
            if candidates:
                cut_point = min(
                    candidates, key=lambda boundary: abs(boundary - preferred_end)
                )
            else:
                cut_point = max_end

            segments.append((current_start, cut_point))
            next_start = max(0.0, cut_point - self.config.overlap_seconds)
            if next_start <= current_start:
                next_start = cut_point
            current_start = next_start

        return segments

    @staticmethod
    def normalize_word(word: str) -> str:
        return re.sub(r"[^\wа-яА-ЯёЁ-]+", "", word).lower()

    def merge_chunk_texts(self, parts: list[str]) -> str:
        merged: list[str] = []

        for part in parts:
            if not part:
                continue

            words = part.split()
            if not merged:
                merged.extend(words)
                continue

            overlap = 0
            max_overlap = min(MAX_WORD_OVERLAP, len(merged), len(words))
            for candidate in range(max_overlap, 0, -1):
                left = [self.normalize_word(word) for word in merged[-candidate:]]
                right = [self.normalize_word(word) for word in words[:candidate]]
                if left == right:
                    overlap = candidate
                    break

            merged.extend(words[overlap:])

        return " ".join(merged).strip()

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [part.strip() for part in parts if part.strip()]

    def deduplicate_sentences(self, text: str) -> str:
        sentences = self.split_sentences(text)
        if not sentences:
            return text.strip()

        merged: list[str] = []
        for sentence in sentences:
            normalized = self.normalize_word(sentence)
            if not normalized:
                continue

            if merged and self.normalize_word(merged[-1]) == normalized:
                continue

            overlap = 0
            max_overlap = min(MAX_SENTENCE_OVERLAP, len(merged))
            for candidate in range(max_overlap, 0, -1):
                left = [self.normalize_word(item) for item in merged[-candidate:]]
                right = [
                    self.normalize_word(item)
                    for item in self.split_sentences(sentence)[:candidate]
                ]
                if left == right:
                    overlap = candidate
                    break

            if overlap:
                continue

            merged.append(sentence)

        return " ".join(merged).strip()

    def transcribe_long_audio(self, model, audio_path: Path) -> str:
        total_duration = self.probe_duration(audio_path)
        silence_boundaries = self.detect_silence_boundaries(audio_path)
        segments = self.build_segments(total_duration, silence_boundaries)
        parts: list[str] = []

        with tempfile.TemporaryDirectory(prefix="gigaam_chunks_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            total_chunks = len(segments)
            progress = ProgressBar(
                total=total_chunks,
                label="[chunks]",
                unit="chunks",
                bytes_mode=False,
            )
            for index, (start_seconds, end_seconds) in enumerate(segments):
                current_duration = max(0.0, end_seconds - start_seconds)
                chunk_path = temp_dir_path / f"chunk_{index:04d}.wav"
                self.export_chunk(audio_path, start_seconds, current_duration, chunk_path)
                parts.append(model.transcribe(str(chunk_path)).strip())
                progress.update(index + 1)
            progress.finish(total_chunks)

        return self.deduplicate_sentences(self.merge_chunk_texts(parts))
