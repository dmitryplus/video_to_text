from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from src.download_strategies.base import VideoDownloadStrategy
from src.progress_bar import ProgressBar


YOUTUBE_VIDEO_FORMAT = (
    "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
    "best[height<=480][ext=mp4]/best[height<=480]/best"
)


class YouTubeDownloadStrategy(VideoDownloadStrategy):
    def can_handle(self, source_url: str) -> bool:
        parsed = urlparse(source_url)
        host = parsed.netloc.lower()
        return any(
            domain in host
            for domain in ("youtube.com", "youtu.be", "youtube-nocookie.com")
        )

    def download(self, source_url: str, target_dir: Path, preferred_stem: str) -> Path:
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
            "format": YOUTUBE_VIDEO_FORMAT,
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

        downloaded_path = self._resolve_downloaded_path(
            info,
            downloaded_path,
            target_dir,
            preferred_stem,
        )
        self._log(f"Видео YouTube скачано: {downloaded_path}")
        return downloaded_path

    @staticmethod
    def _resolve_downloaded_path(
        info: dict,
        prepared_path: Path,
        target_dir: Path,
        preferred_stem: str,
    ) -> Path:
        if prepared_path.exists():
            return prepared_path

        requested_downloads = info.get("requested_downloads") or []
        for item in requested_downloads:
            filepath = item.get("filepath")
            if filepath and Path(filepath).exists():
                return Path(filepath)

        candidates = sorted(
            target_dir.glob(f"{preferred_stem}.*"),
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

        raise SystemExit("yt-dlp завершился без ошибки, но скачанный файл не найден.")
