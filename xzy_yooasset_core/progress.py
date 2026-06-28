from __future__ import annotations

import time
from typing import Any

from .utils import format_duration

try:  # pragma: no cover - optional dependency
    from rich.console import Console
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.table import Column
except Exception:  # pragma: no cover - fallback when rich is unavailable
    Console = None  # type: ignore[assignment]
    Progress = None  # type: ignore[assignment]
    BarColumn = None  # type: ignore[assignment]
    MofNCompleteColumn = None  # type: ignore[assignment]
    SpinnerColumn = None  # type: ignore[assignment]
    TextColumn = None  # type: ignore[assignment]
    TimeElapsedColumn = None  # type: ignore[assignment]
    TimeRemainingColumn = None  # type: ignore[assignment]
    Column = None  # type: ignore[assignment]


class ProgressReporter:
    def __init__(self, total: int, style: str, every: int) -> None:
        self.total = max(total, 0)
        self.style = "none" if every <= 0 else style
        self.every = max(every, 0)
        self.start_time = time.time()
        self.last_len = 0
        self._progress: Any = None
        self._task_id: Any = None
        self._rich_enabled = self.style == "bar" and Progress is not None

        if self._rich_enabled and self.total > 0:
            console = Console(stderr=True, highlight=False, soft_wrap=True)  # type: ignore[misc]
            self._progress = Progress(
                SpinnerColumn(style="cyan"),
                TextColumn("[bold cyan]{task.description}", table_column=Column(ratio=2)),  # type: ignore[misc]
                BarColumn(bar_width=None, complete_style="cyan", finished_style="green", pulse_style="cyan"),
                MofNCompleteColumn(),
                TextColumn("assets={task.fields[assets]}", style="green"),
                TextColumn("errors={task.fields[errors]}", style="red"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                TextColumn("{task.fields[current]}", style="dim", table_column=Column(ratio=3)),  # type: ignore[misc]
                console=console,
                transient=False,
                auto_refresh=True,
                refresh_per_second=10,
                expand=True,
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self._progress.start()
            self._task_id = self._progress.add_task(
                "bundles",
                total=self.total,
                assets=0,
                errors=0,
                current="",
            )

    def _should_emit(self, processed: int, force: bool) -> bool:
        if self.style == "none" or self.total <= 0:
            return False
        if force:
            return True
        return not self.every or processed % self.every == 0 or processed == self.total

    def update(self, processed: int, asset_count: int, error_count: int, current: str = "", force: bool = False) -> None:
        if not self._should_emit(processed, force):
            return

        elapsed = time.time() - self.start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (self.total - processed) / rate if rate > 0 else 0

        if self._progress is not None:
            self._progress.update(
                self._task_id,
                completed=processed,
                total=self.total,
                assets=asset_count,
                errors=error_count,
                current=current,
            )
            return

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
        bar = "█" * filled + "░" * (width - filled)
        message = (
            f"\r[{bar}] {processed}/{self.total} {percent:5.1f}% "
            f"assets={asset_count} errors={error_count} "
            f"elapsed={format_duration(elapsed)} eta={format_duration(remaining)} {current}"
        )
        padding = " " * max(0, self.last_len - len(message))
        print(message + padding, end="", flush=True)
        self.last_len = len(message)

    def finish(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            return
        if self.style == "bar" and self.last_len:
            print()
