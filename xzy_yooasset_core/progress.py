from __future__ import annotations

import time

from .utils import format_duration


class ProgressReporter:
    def __init__(self, total: int, style: str, every: int) -> None:
        self.total = max(total, 0)
        self.style = "none" if every <= 0 else style
        self.every = max(every, 0)
        self.start_time = time.time()
        self.last_len = 0

    def update(self, processed: int, asset_count: int, error_count: int, current: str = "", force: bool = False) -> None:
        if self.style == "none" or self.total <= 0:
            return
        if not force and self.every and processed % self.every != 0 and processed != self.total:
            return

        elapsed = time.time() - self.start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (self.total - processed) / rate if rate > 0 else 0
        percent = (processed / self.total) * 100 if self.total else 100

        if self.style == "lines":
            print(
                f"[progress] {processed}/{self.total} {percent:5.1f}% "
                f"assets={asset_count} errors={error_count} "
                f"elapsed={format_duration(elapsed)} eta={format_duration(remaining)} {current}",
                flush=True,
            )
            return

        width = 28
        filled = int(width * processed / self.total) if self.total else width
        bar = "#" * filled + "-" * (width - filled)
        message = (
            f"\r[{bar}] {processed}/{self.total} {percent:5.1f}% "
            f"assets={asset_count} errors={error_count} "
            f"elapsed={format_duration(elapsed)} eta={format_duration(remaining)} {current}"
        )
        padding = " " * max(0, self.last_len - len(message))
        print(message + padding, end="", flush=True)
        self.last_len = len(message)

    def finish(self) -> None:
        if self.style == "bar" and self.last_len:
            print()
