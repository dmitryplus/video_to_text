from __future__ import annotations

import sys
import time
from typing import TextIO


DEFAULT_PROGRESS_BAR_WIDTH = 30
DEFAULT_PROGRESS_UPDATE_SECONDS = 0.2


class ProgressBar:
    def __init__(
        self,
        total: int = 0,
        *,
        label: str = "[file]",
        unit: str = "items",
        bytes_mode: bool = True,
        width: int = DEFAULT_PROGRESS_BAR_WIDTH,
        update_interval: float = DEFAULT_PROGRESS_UPDATE_SECONDS,
        output: TextIO = sys.stderr,
    ):
        self.total = total
        self.label = label
        self.unit = unit
        self.bytes_mode = bytes_mode
        self.width = width
        self.update_interval = update_interval
        self.output = output
        self.started_at = time.monotonic()
        self.last_rendered_at = 0.0

    def update(self, current: int) -> None:
        now = time.monotonic()
        if now - self.last_rendered_at < self.update_interval:
            return
        self._render(current, finished=False)
        self.last_rendered_at = now

    def finish(self, current: int) -> None:
        self._render(current, finished=True)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB")
        value = float(size_bytes)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{size_bytes} B"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds <= 0:
            return "0s"
        total_seconds = int(seconds)
        minutes, sec = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h{minutes:02d}m"
        if minutes:
            return f"{minutes}m{sec:02d}s"
        return f"{sec}s"

    def _render(self, current: int, *, finished: bool) -> None:
        elapsed = max(time.monotonic() - self.started_at, 0.001)
        speed = current / elapsed

        if self.total > 0:
            progress_text = self._render_known_total(current, speed)
        else:
            speed_text = self._format_speed(speed)
            progress_text = (
                f"\r\033[K{self.label} processed {self._format_value(current)} "
                f"{speed_text}"
            )

        print(
            progress_text,
            end="\n" if finished else "",
            file=self.output,
            flush=True,
        )

    def _render_known_total(
        self,
        current: int,
        speed: float,
    ) -> str:
        ratio = min(current / self.total, 1.0)
        filled = int(self.width * ratio)
        if filled >= self.width:
            bar = "=" * self.width
        else:
            bar = "=" * filled + ">" + "." * (self.width - filled - 1)

        percent = ratio * 100
        remaining = max(self.total - current, 0)
        eta = self._format_duration(remaining / speed) if speed > 0 else "--"
        return (
            f"\r\033[K{self.label} {percent:6.2f}% [{bar}] "
            f"{self._format_value(current)} / {self._format_value(self.total)} "
            f"{self._format_speed(speed)} ETA {eta}"
        )

    def _format_value(self, value: int) -> str:
        if self.bytes_mode:
            return self._format_size(value)
        return f"{value} {self.unit}"

    def _format_speed(self, speed: float) -> str:
        if self.bytes_mode:
            return f"{self._format_size(int(speed))}/s"
        return f"{speed:.2f} {self.unit}/s"
