from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


def parse_csv(value: str | None) -> set[str] | None:
    if not value:
        return None
    items = {part.strip() for part in value.split(",") if part.strip()}
    return items or None


def parse_csv_lower(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def safe_name(value: str, fallback: str = "unnamed", max_len: int = 96) -> str:
    value = value.replace("\\", "/").split("/")[-1]
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value).strip(" .")
    if not value:
        value = fallback
    return value[:max_len]


def normalize_ref(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def short_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
