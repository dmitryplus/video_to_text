from __future__ import annotations

from src.download_strategies.requests_strategy import RequestsDownloadStrategy


class HttpDownloadStrategy(RequestsDownloadStrategy):
    def can_handle(self, source_url: str) -> bool:
        return True
