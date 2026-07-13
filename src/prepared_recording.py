from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path


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
