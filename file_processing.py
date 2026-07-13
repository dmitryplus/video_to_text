from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from progress_bar import ProgressBar


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
DOWNLOAD_RETRIES = 3


@dataclass
class PreparedRecording:
    audio_path: Path
    source_path: Path | None = None
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self.temp_dir is not None:
            self.temp_dir.cleanup()
            self.temp_dir = None

    def __enter__(self) -> PreparedRecording:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


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
    def _is_youtube_url(value: str) -> bool:
        parsed = urlparse(value)
        host = parsed.netloc.lower()
        return any(
            domain in host
            for domain in ("youtube.com", "youtu.be", "youtube-nocookie.com")
        )

    @staticmethod
    def _requires_audio_extraction(path: Path) -> bool:
        return path.suffix.lower() in VIDEO_SUFFIXES

    def _prepare_remote_media(self, source_url: str) -> PreparedRecording:
        cache_prefix = self._build_cache_prefix(source_url)
        if self._is_youtube_url(source_url):
            return self._prepare_youtube_media(source_url, cache_prefix)

        if self.keep_source_media or self.keep_extracted_audio:
            cache_dir = self._ensure_cache_dir()
            download_url = self._resolve_download_url(source_url)
            downloaded_path = self._download_file(
                download_url,
                cache_dir,
                preferred_stem=cache_prefix,
            )
            audio_path = cache_dir / f"{cache_prefix}.wav"
            if audio_path.exists():
                self._log(f"Найден готовый WAV в кэше: {audio_path}")
            else:
                self._extract_audio(downloaded_path, audio_path)
            return PreparedRecording(audio_path=audio_path, source_path=downloaded_path)

        temp_dir = tempfile.TemporaryDirectory(prefix="recording_source_")
        temp_path = Path(temp_dir.name)
        download_url = self._resolve_download_url(source_url)
        downloaded_path = self._download_file(
            download_url,
            temp_path,
            preferred_stem=cache_prefix,
        )
        audio_path = temp_path / "recording.wav"
        self._extract_audio(downloaded_path, audio_path)
        return PreparedRecording(
            audio_path=audio_path,
            source_path=downloaded_path,
            temp_dir=temp_dir,
        )

    def _prepare_youtube_media(self, source_url: str, cache_prefix: str) -> PreparedRecording:
        if self.keep_source_media or self.keep_extracted_audio:
            cache_dir = self._ensure_cache_dir()
            audio_path = cache_dir / f"{cache_prefix}.wav"
            if audio_path.exists():
                self._log(f"Найден готовый WAV в кэше: {audio_path}")
                source_path = self._find_cached_youtube_source(cache_dir, cache_prefix)
                return PreparedRecording(audio_path=audio_path, source_path=source_path)

            downloaded_path = self._download_youtube_video(source_url, cache_dir, cache_prefix)
            self._extract_audio(downloaded_path, audio_path)
            source_path = downloaded_path
            if not self.keep_source_media:
                downloaded_path.unlink(missing_ok=True)
                source_path = None
            return PreparedRecording(audio_path=audio_path, source_path=source_path)

        temp_dir = tempfile.TemporaryDirectory(prefix="youtube_source_")
        temp_path = Path(temp_dir.name)
        downloaded_path = self._download_youtube_video(source_url, temp_path, cache_prefix)
        audio_path = temp_path / "recording.wav"
        self._extract_audio(downloaded_path, audio_path)
        return PreparedRecording(
            audio_path=audio_path,
            source_path=downloaded_path,
            temp_dir=temp_dir,
        )

    @staticmethod
    def _find_cached_youtube_source(cache_dir: Path, cache_prefix: str) -> Path | None:
        candidates = sorted(
            (
                candidate
                for candidate in cache_dir.glob(f"{cache_prefix}.*")
                if candidate.suffix.lower() != ".wav"
            ),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _download_youtube_video(
        self, source_url: str, target_dir: Path, preferred_stem: str
    ) -> Path:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise SystemExit(
                "Не удалось импортировать yt-dlp. "
                "Установите зависимости: pip install -r requirements.txt"
            ) from exc

        target_template = str(target_dir / f"{preferred_stem}.%(ext)s")
        progress_bar: ProgressBar | None = None
        progress_total = 0

        def progress_hook(event: dict) -> None:
            nonlocal progress_bar, progress_total
            status = event.get("status")
            downloaded = int(event.get("downloaded_bytes") or 0)
            total = int(event.get("total_bytes") or event.get("total_bytes_estimate") or 0)

            if status == "downloading":
                if progress_bar is None or total != progress_total:
                    progress_bar = ProgressBar(total=total, label="[YouTube]")
                    progress_total = total
                progress_bar.update(downloaded)
            elif status == "finished" and progress_bar is not None:
                finished_size = downloaded or total
                progress_bar.finish(finished_size)

        self._log("Скачиваю видео с YouTube")
        options = {
            "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/best",
            "outtmpl": target_template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [progress_hook],
        }
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(source_url, download=True)
                downloaded_path = Path(downloader.prepare_filename(info))
        except Exception as exc:
            raise SystemExit(f"Не удалось скачать видео с YouTube: {exc}") from exc

        if downloaded_path.exists():
            self._log(f"Видео YouTube скачано: {downloaded_path}")
            return downloaded_path

        requested_downloads = info.get("requested_downloads") or []
        for item in requested_downloads:
            filepath = item.get("filepath")
            if filepath and Path(filepath).exists():
                path = Path(filepath)
                self._log(f"Видео YouTube скачано: {path}")
                return path

        candidates = sorted(
            target_dir.glob(f"{preferred_stem}.*"),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            self._log(f"Видео YouTube скачано: {candidates[0]}")
            return candidates[0]

        raise SystemExit("yt-dlp завершился без ошибки, но скачанный файл не найден.")

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

    def _resolve_download_url(self, source_url: str) -> str:
        parsed = urlparse(source_url)
        if "yandex.ru" in parsed.netloc or "yandex.com" in parsed.netloc:
            self._log("Запрашиваю прямую ссылку на скачивание из Yandex Disk")
            response = requests.get(
                "https://cloud-api.yandex.net/v1/disk/public/resources/download",
                params={"public_key": source_url},
                timeout=30,
            )
            response.raise_for_status()
            href = response.json().get("href")
            if not href:
                raise SystemExit("Не удалось получить ссылку для скачивания из Yandex Disk.")
            self._log("Прямая ссылка Yandex Disk получена")
            return href
        return source_url

    def _download_file(self, download_url: str, target_dir: Path, preferred_stem: str) -> Path:
        last_error: Exception | None = None

        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            part_path: Path | None = None
            try:
                with requests.get(download_url, stream=True, timeout=120) as response:
                    response.raise_for_status()
                    filename = self._infer_filename(
                        download_url,
                        response.headers,
                        preferred_stem,
                    )
                    target_path = target_dir / filename
                    expected_size = int(response.headers.get("content-length", "0") or "0")

                    if (
                        target_path.exists()
                        and expected_size > 0
                        and target_path.stat().st_size == expected_size
                    ):
                        self._log(f"Найден скачанный файл в кэше: {target_path}")
                        return target_path

                    part_path = target_path.with_suffix(target_path.suffix + ".part")
                    if part_path.exists():
                        self._log(f"Удаляю незавершенный файл: {part_path}")
                        part_path.unlink()

                    size_hint = (
                        f"{expected_size / (1024 * 1024):.1f} MB"
                        if expected_size > 0
                        else "размер неизвестен"
                    )
                    self._log(
                        f"Скачивание {target_path.name}, попытка {attempt}/{DOWNLOAD_RETRIES} "
                        f"({size_hint})"
                    )

                    downloaded_bytes = 0
                    progress = ProgressBar(total=expected_size)
                    with part_path.open("wb") as file_obj:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            file_obj.write(chunk)
                            downloaded_bytes += len(chunk)
                            progress.update(downloaded_bytes)

                    actual_size = part_path.stat().st_size
                    if expected_size > 0 and actual_size != expected_size:
                        raise IOError(
                            f"Скачанный файл неполный: {part_path.name} "
                            f"({actual_size} из {expected_size} байт)."
                        )

                    part_path.replace(target_path)
                    progress.finish(actual_size)
                    self._log(
                        f"Скачивание завершено: {target_path} "
                        f"({actual_size / (1024 * 1024):.1f} MB)"
                    )
                    return target_path
            except (requests.RequestException, OSError) as exc:
                last_error = exc
                if part_path is not None and part_path.exists():
                    self._log(f"Удаляю битый временный файл: {part_path}")
                    part_path.unlink(missing_ok=True)
                if attempt < DOWNLOAD_RETRIES:
                    self._log(f"Ошибка скачивания, повторяю попытку: {exc}")
                    continue
                break

        raise SystemExit(f"Не удалось скачать файл: {last_error}")

    @staticmethod
    def _infer_filename(
        download_url: str,
        headers: requests.structures.CaseInsensitiveDict,
        preferred_stem: str,
    ) -> str:
        disposition = headers.get("content-disposition", "")
        filename_match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
        if filename_match:
            original_name = Path(filename_match.group(1)).name
            suffix = Path(original_name).suffix or ".bin"
            return f"{preferred_stem}{suffix}"

        parsed = urlparse(download_url)
        name = Path(parsed.path).name
        if name:
            suffix = Path(name).suffix or ".bin"
            return f"{preferred_stem}{suffix}"
        return f"{preferred_stem}.bin"

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
