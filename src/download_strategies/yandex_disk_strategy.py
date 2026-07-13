from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests

from src.download_strategies.requests_strategy import RequestsDownloadStrategy


class YandexDiskDownloadStrategy(RequestsDownloadStrategy):
    def can_handle(self, source_url: str) -> bool:
        parsed = urlparse(source_url)
        host = parsed.netloc.lower()
        return "yandex.ru" in host or "yandex.com" in host

    def download(self, source_url: str, target_dir: Path, preferred_stem: str) -> Path:
        self._log("Запрашиваю прямую ссылку на скачивание из Яндекс.Диска")
        response = requests.get(
            "https://cloud-api.yandex.net/v1/disk/public/resources/download",
            params={"public_key": source_url},
            timeout=30,
        )
        response.raise_for_status()
        href = response.json().get("href")
        if not href:
            raise SystemExit("Не удалось получить ссылку для скачивания из Яндекс.Диска.")
        self._log("Прямая ссылка Яндекс.Диска получена")
        return self._download_file(href, target_dir, preferred_stem)
