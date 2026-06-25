from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .manifest import iter_manifest_files
from .models import BundleCandidate, RawFileCandidate, YooRoot


def detect_yoo_layout(path: Path) -> str:
    if any(path.glob("*/*.bundle")):
        return "streaming_assets"
    return "hot_update"


def resolve_yoo_roots(game_root: str, yoo_root: str, source_layout: str) -> list[YooRoot]:
    if yoo_root:
        root = Path(yoo_root).expanduser().resolve()
        return [YooRoot(root, detect_yoo_layout(root))]
    if not game_root:
        raise SystemExit("Provide --game-root or --yoo-root.")

    root = Path(game_root).expanduser().resolve()
    if root.name.lower() == "yoo":
        return [YooRoot(root, detect_yoo_layout(root))]

    if root.name == "XzyLauncher_Data":
        data_root = root
    else:
        data_root = root / "XzyLauncher_Data"

    candidates: list[YooRoot] = []
    hot_root = data_root / "yoo"
    streaming_root = data_root / "StreamingAssets" / "yoo"
    if source_layout in ("all", "hot") and hot_root.exists():
        candidates.append(YooRoot(hot_root, "hot_update"))
    if source_layout in ("all", "streaming") and streaming_root.exists():
        candidates.append(YooRoot(streaming_root, "streaming_assets"))
    return candidates


def iter_package_roots(yoo_roots: Iterable[YooRoot], packages: set[str] | None) -> Iterable[tuple[YooRoot, Path]]:
    for yoo_root in yoo_roots:
        if not yoo_root.path.exists():
            continue
        for package_root in sorted(p for p in yoo_root.path.iterdir() if p.is_dir()):
            if packages and package_root.name not in packages:
                continue
            yield yoo_root, package_root


def iter_bundle_files(package_roots: Iterable[tuple[YooRoot, Path]]) -> Iterable[BundleCandidate]:
    for yoo_root, package_root in package_roots:
        if yoo_root.layout == "hot_update":
            bundle_dir = package_root / "BundleFiles"
            if not bundle_dir.exists():
                continue
            for data_path in sorted(bundle_dir.rglob("__data")):
                if data_path.is_file():
                    yield BundleCandidate(yoo_root, package_root, data_path, data_path.parent.name)
            continue

        for data_path in sorted(package_root.rglob("*.bundle")):
            if data_path.is_file():
                yield BundleCandidate(yoo_root, package_root, data_path, data_path.stem)


def iter_raw_files(package_roots: Iterable[tuple[YooRoot, Path]]) -> Iterable[RawFileCandidate]:
    for yoo_root, package_root in package_roots:
        for data_path in sorted(package_root.rglob("*.rawfile")):
            if data_path.is_file():
                yield RawFileCandidate(yoo_root, package_root, data_path, data_path.stem)


def package_report_row(yoo_root: YooRoot, package_root: Path) -> dict[str, object]:
    bundle_dir = package_root / "BundleFiles"
    bundle_file_count = 0
    if bundle_dir.exists():
        bundle_file_count = sum(1 for p in bundle_dir.rglob("__data") if p.is_file())

    streaming_bundle_count = sum(1 for p in package_root.rglob("*.bundle") if p.is_file())
    rawfile_count = sum(1 for p in package_root.rglob("*.rawfile") if p.is_file())
    bundle_count = bundle_file_count + streaming_bundle_count
    manifest_files = list(iter_manifest_files(yoo_root, package_root))

    all_files = [p for p in package_root.rglob("*") if p.is_file()]
    return {
        "root": str(yoo_root.path),
        "layout": yoo_root.layout,
        "package": package_root.name,
        "has_bundle_files": bundle_count > 0,
        "bundle_count": bundle_count,
        "bundle_file_count": bundle_file_count,
        "streaming_bundle_count": streaming_bundle_count,
        "rawfile_count": rawfile_count,
        "manifest_file_count": len(manifest_files),
        "manifest_bytes": sum(p.stat().st_size for p in manifest_files),
        "total_files": len(all_files),
        "total_bytes": sum(p.stat().st_size for p in all_files),
    }
