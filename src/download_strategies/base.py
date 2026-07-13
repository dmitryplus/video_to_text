from __future__ import annotations

from pathlib import Path
from typing import Callable


LogFn = Callable[[str], None]


class VideoDownloadStrategy:
    def __init__(self, log: LogFn):
        self._log = log

    def can_handle(self, source_url: str) -> bool:
        raise NotImplementedError

    def download(self, source_url: str, target_dir: Path, preferred_stem: str) -> Path:
        raise NotImplementedError
