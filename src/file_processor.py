from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from src.download_strategies import (
    HttpDownloadStrategy,
    VideoDownloadStrategy,
    VkVideoDownloadStrategy,
    YandexDiskDownloadStrategy,
    YouTubeDownloadStrategy,
)
from src.prepared_recording import PreparedRecording


VIDEO_SUFFIXES = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".flv",
    ".wmv",
}
DEFAULT_CACHE_DIR = ".cache/recordings"


class FileProcessor:
    def __init__(
        self,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        keep_source_media: bool = False,
        keep_extracted_audio: bool = False,
    ):
        self.cache_dir = Path(cache_dir).expanduser()
        self.keep_source_media = keep_source_media
        self.keep_extracted_audio = keep_extracted_audio
        self.download_strategies: list[VideoDownloadStrategy] = [
            YouTubeDownloadStrategy(self._log),
            VkVideoDownloadStrategy(self._log),
            YandexDiskDownloadStrategy(self._log),
            HttpDownloadStrategy(self._log),
        ]

    def prepare(self, input_ref: str) -> PreparedRecording:
        if self._is_url(input_ref):
            self._log(f"Подготовка записи по URL: {input_ref}")
            return self._prepare_remote_media(input_ref)

        local_path = Path(input_ref).expanduser()
        if not local_path.exists():
            raise SystemExit(f"Файл не найден: {local_path}")

        if self._requires_audio_extraction(local_path):
            self._log(f"Локальный видеофайл, извлекаю аудио: {local_path}")
            return self._extract_local_media_audio(local_path)

        self._log(f"Использую локальный аудиофайл: {local_path}")
        return PreparedRecording(audio_path=local_path, source_path=local_path)

    @staticmethod
    def _is_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _requires_audio_extraction(path: Path) -> bool:
        return path.suffix.lower() in VIDEO_SUFFIXES

    def _prepare_remote_media(self, source_url: str) -> PreparedRecording:
        cache_prefix = self._build_cache_prefix(source_url)
        download_strategy = self._select_download_strategy(source_url)

        if self.keep_source_media or self.keep_extracted_audio:
            cache_dir = self._ensure_cache_dir()
            audio_path = cache_dir / f"{cache_prefix}.wav"
            if audio_path.exists():
                self._log(f"Найден готовый WAV в кэше: {audio_path}")
                source_path = self._find_cached_source(cache_dir, cache_prefix)
                return PreparedRecording(audio_path=audio_path, source_path=source_path)

            downloaded_path = download_strategy.download(source_url, cache_dir, cache_prefix)
            self._extract_audio(downloaded_path, audio_path)
            source_path = downloaded_path
            if not self.keep_source_media:
                downloaded_path.unlink(missing_ok=True)
                source_path = None
            return PreparedRecording(audio_path=audio_path, source_path=source_path)

        temp_dir = tempfile.TemporaryDirectory(prefix="recording_source_")
        temp_path = Path(temp_dir.name)
        downloaded_path = download_strategy.download(source_url, temp_path, cache_prefix)
        audio_path = temp_path / "recording.wav"
        self._extract_audio(downloaded_path, audio_path)
        return PreparedRecording(
            audio_path=audio_path,
            source_path=downloaded_path,
            temp_dir=temp_dir,
        )

    def _select_download_strategy(self, source_url: str) -> VideoDownloadStrategy:
        for strategy in self.download_strategies:
            if strategy.can_handle(source_url):
                return strategy
        raise SystemExit(f"Не найден загрузчик для URL: {source_url}")

    @staticmethod
    def _find_cached_source(cache_dir: Path, cache_prefix: str) -> Path | None:
        candidates = sorted(
            (
                candidate
                for candidate in cache_dir.glob(f"{cache_prefix}.*")
                if candidate.suffix.lower() not in {".wav", ".part"}
            ),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _extract_local_media_audio(self, source_path: Path) -> PreparedRecording:
        if self.keep_extracted_audio:
            cache_dir = self._ensure_cache_dir()
            cache_prefix = self._build_cache_prefix(str(source_path.resolve()))
            audio_path = cache_dir / f"{cache_prefix}.wav"
            if audio_path.exists():
                self._log(f"Найден готовый WAV в кэше: {audio_path}")
            else:
                self._extract_audio(source_path, audio_path)
            return PreparedRecording(audio_path=audio_path, source_path=source_path)

        temp_dir = tempfile.TemporaryDirectory(prefix="recording_audio_")
        temp_path = Path(temp_dir.name)
        audio_path = temp_path / f"{source_path.stem}.wav"
        self._extract_audio(source_path, audio_path)
        return PreparedRecording(
            audio_path=audio_path,
            source_path=source_path,
            temp_dir=temp_dir,
        )

    def _ensure_cache_dir(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir

    @staticmethod
    def _log(message: str) -> None:
        print(f"[file] {message}", file=sys.stderr, flush=True)

    @staticmethod
    def _build_cache_prefix(value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        return f"recording_{digest}"

    @staticmethod
    def _extract_audio(source_path: Path, audio_path: Path) -> None:
        print(
            f"[file] Извлекаю аудио: {source_path} -> {audio_path}",
            file=sys.stderr,
            flush=True,
        )
        command = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                f"Не удалось извлечь аудиодорожку из: {source_path}"
            ) from exc
