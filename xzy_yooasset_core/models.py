from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class YooRoot:
    path: Path
    layout: str


@dataclass(frozen=True)
class BundleCandidate:
    root: YooRoot
    package_root: Path
    data_path: Path
    hash_name: str


@dataclass(frozen=True)
class RawFileCandidate:
    root: YooRoot
    package_root: Path
    data_path: Path
    hash_name: str


@dataclass
class BundleInput:
    layout: str
    package: str
    hash_name: str
    source_path: Path
    mode: str
    unity_bytes: bytes | None
    raw_head: bytes
    decoded_head: bytes


@dataclass
class ManifestIndex:
    rows: list[dict[str, Any]]
    hash_refs: set[str]
    asset_refs: tuple[str, ...]
    asset_cache: dict[str, tuple[str, str]]


@dataclass
class ExportOptions:
    out_root: Path
    execute: bool
    keep_bundles: bool
    no_export: bool
    categories: set[str] | None
    types: set[str] | None
    ui_packages: set[str]
    model_packages: set[str]
    effects_packages: set[str]
    animation_packages: set[str]
    unitypy: Any | None = None


@dataclass
class ExportContext:
    options: ExportOptions
    used_outputs: set[Path]
    manifest_index: ManifestIndex | None = None
