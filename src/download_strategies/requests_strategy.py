from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.download_strategies.base import VideoDownloadStrategy
from src.progress_bar import ProgressBar


DOWNLOAD_RETRIES = 3


class RequestsDownloadStrategy(VideoDownloadStrategy):
    def can_handle(self, source_url: str) -> bool:
        return True

    def download(self, source_url: str, target_dir: Path, preferred_stem: str) -> Path:
        return self._download_file(source_url, target_dir, preferred_stem)

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
        filename_match = re.search(
            r'filename\*?=(?:UTF-8'')?"?([^";]+)"?',
            disposition,
        )
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
