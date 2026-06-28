from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import BrokenExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bundle import classify_bundle
from .constants import ASSET_FIELDS, BUNDLE_FIELDS, MANIFEST_REF_FIELDS, OUTPUT_CATEGORIES, PACKAGE_FIELDS
from .discovery import iter_bundle_files, iter_package_roots, iter_raw_files, package_report_row, resolve_yoo_roots
from .exporter import (
    category_is_enabled,
    copy_file,
    export_object,
    import_unitypy,
    load_unity_env,
    raw_bundle_row,
    rawfile_output_path,
    rawfile_row,
    write_prefab_graph,
    write_bytes,
)
from .manifest import build_manifest_index, manifest_match_for_bundle
from .models import BundleCandidate, BundleInput, ExportContext, ExportOptions, ManifestIndex, YooRoot
from .progress import ProgressReporter
from .utils import parse_csv, parse_csv_lower, write_csv


@dataclass
class BundleProcessResult:
    index: int
    progress_label: str
    bundle_row: dict[str, Any] | None
    asset_rows: list[dict[str, Any]]
    error: dict[str, Any] | None


_WORKER_OPTIONS: ExportOptions | None = None
_WORKER_MANIFEST_INDEX: ManifestIndex | None = None
_WORKER_UNITYPY: Any | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decrypt and export local YooAssets/Unity asset bundles that use a tail-16 XOR key.",
    )
    parser.add_argument("--game-root", default="", help="Game root containing XzyLauncher_Data. Scans hot-update yoo and StreamingAssets/yoo by default.")
    parser.add_argument("--yoo-root", default="", help="Direct path to one YooAssets root. Overrides --game-root.")
    parser.add_argument(
        "--source-layout",
        choices=("all", "hot", "streaming"),
        default="all",
        help="Which YooAssets source layout to scan when --game-root is used.",
    )
    parser.add_argument("--out", default="xzy_assets_out", help="Output directory.")
    parser.add_argument("--packages", default="", help="Comma-separated package names, for example Icon,Main,Spine.")
    parser.add_argument("--categories", default="", help="Comma-separated output categories to export, for example ui,bgm,models,effects. Empty means all categories.")
    parser.add_argument("--types", default="", help="Comma-separated Unity object type names to export, for example Texture2D,Sprite,AudioClip. Empty means all types.")
    parser.add_argument("--limit", type=int, default=30, help="Maximum bundles to process. Use 0 for all.")
    parser.add_argument("--execute", action="store_true", help="Write exported files and index files. Without this, run as dry-run.")
    parser.add_argument("--no-export", action="store_true", help="Classify/decrypt bundles only; skip UnityPy object export.")
    parser.add_argument("--copy-rawfiles", action="store_true", help="Copy local .rawfile payloads under assets/raw and add them to assets.csv.")
    parser.add_argument("--keep-bundles", action="store_true", help="Write decrypted UnityFS bundles under decrypted_bundles/.")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes for bundle classification/export. Use 1 for serial mode.")
    parser.add_argument("--progress-every", type=int, default=25, help="Print progress every N processed bundles. Use 0 to disable.")
    parser.add_argument("--progress-style", choices=("bar", "lines", "none"), default="bar", help="Progress display style. Use lines for log files.")
    parser.add_argument("--no-manifest-check", action="store_true", help="Skip manifest/catalog static reference scan.")
    parser.add_argument("--list-packages", action="store_true", help="Print package report and exit.")
    parser.add_argument("--fail-on-error", action="store_true", help="Return exit code 2 when bundle-level errors are found.")
    parser.add_argument("--ui-packages", default="Icon,Background,Main,Spine", help="Packages whose Texture2D/Sprite outputs should be grouped under assets/ui.")
    parser.add_argument("--model-packages", default="CharacterMesh,Art3D", help="Packages grouped under assets/models.")
    parser.add_argument("--effects-packages", default="BattlePacket,Effect,Effects,Vfx,VFX,Fx", help="Packages grouped under assets/effects.")
    parser.add_argument(
        "--animation-packages",
        default="Spine,AnimationPacket,CharacterTimeline,CharacterController,CharacterPerformance",
        help="Packages grouped under assets/animation for non-image objects.",
    )
    return parser


def validate_roots(yoo_roots: list[YooRoot]) -> None:
    if not yoo_roots:
        raise SystemExit(
            "YooAssets root not found. Expected XzyLauncher_Data/yoo and/or "
            "XzyLauncher_Data/StreamingAssets/yoo under --game-root."
        )
    missing_roots = [root.path for root in yoo_roots if not root.path.exists()]
    if missing_roots:
        raise SystemExit(f"YooAssets root not found: {missing_roots[0]}")


def build_export_options(args: argparse.Namespace, out_root: Path, categories: set[str] | None, types: set[str] | None, unitypy: Any | None) -> ExportOptions:
    return ExportOptions(
        out_root=out_root,
        execute=args.execute,
        keep_bundles=args.keep_bundles,
        no_export=args.no_export,
        categories=categories,
        types=types,
        ui_packages=parse_csv_lower(args.ui_packages),
        model_packages=parse_csv_lower(args.model_packages),
        effects_packages=parse_csv_lower(args.effects_packages),
        animation_packages=parse_csv_lower(args.animation_packages),
        unitypy=unitypy,
    )


def bundle_row_for(bundle: BundleInput, manifest_index: ManifestIndex | None) -> dict[str, Any]:
    manifest_reference, manifest_match = manifest_match_for_bundle(bundle.hash_name, manifest_index)
    return {
        "layout": bundle.layout,
        "package": bundle.package,
        "bundle_hash": bundle.hash_name,
        "mode": bundle.mode,
        "source": str(bundle.source_path),
        "length": bundle.source_path.stat().st_size,
        "raw_head": bundle.raw_head[:16].hex(" "),
        "decoded_head": bundle.decoded_head[:16].hex(" ") if bundle.decoded_head else "",
        "manifest_reference": manifest_reference,
        "manifest_match": manifest_match,
    }


def process_bundle_candidate(
    index: int,
    candidate: BundleCandidate,
    options: ExportOptions,
    manifest_index: ManifestIndex | None,
    unitypy: Any | None,
) -> BundleProcessResult:
    package_root = candidate.package_root
    data_path = candidate.data_path
    progress_label = f"{candidate.root.layout}/{package_root.name}/{candidate.hash_name}"
    asset_rows: list[dict[str, Any]] = []

    try:
        wants_raw_bundle = category_is_enabled("raw", options)
        load_bundle_bytes = not options.no_export or options.keep_bundles or wants_raw_bundle
        bundle = classify_bundle(
            data_path,
            package_root,
            candidate.root.layout,
            candidate.hash_name,
            load_bytes=load_bundle_bytes,
        )
        bundle_row = bundle_row_for(bundle, manifest_index)

        local_ctx = ExportContext(options=options, used_outputs=set(), manifest_index=manifest_index)
        if bundle.mode.endswith("_unityfs") and bundle.unity_bytes:
            if options.keep_bundles:
                target = options.out_root / "decrypted_bundles" / bundle.layout / bundle.package / f"{bundle.hash_name}.bundle"
                write_bytes(target, bundle.unity_bytes, options.execute)

            if not options.no_export:
                env = load_unity_env(unitypy, bundle.unity_bytes)
                for obj in env.objects:
                    asset_rows.extend(export_object(obj, bundle, local_ctx))
                asset_rows.extend(write_prefab_graph(local_ctx, bundle))
        elif bundle.unity_bytes:
            if category_is_enabled("raw", options):
                target = options.out_root / "raw" / bundle.layout / bundle.package / f"{bundle.hash_name}.bin"
                write_bytes(target, bundle.unity_bytes, options.execute)
                status = "exported_raw_bundle" if options.execute else "listed_raw_bundle"
                asset_rows.append(raw_bundle_row(bundle, target, status, options.out_root, manifest_index))

        return BundleProcessResult(index, progress_label, bundle_row, asset_rows, None)
    except Exception as exc:
        return BundleProcessResult(
            index,
            progress_label,
            None,
            [],
            {
                "source": str(data_path),
                "error": str(exc),
                "trace": traceback.format_exc(limit=6),
            },
        )


def init_bundle_worker(options: ExportOptions, manifest_index: ManifestIndex | None) -> None:
    global _WORKER_OPTIONS, _WORKER_MANIFEST_INDEX, _WORKER_UNITYPY

    _WORKER_OPTIONS = options
    _WORKER_MANIFEST_INDEX = manifest_index
    _WORKER_UNITYPY = None
    if not options.no_export:
        _WORKER_UNITYPY = import_unitypy()
        _WORKER_OPTIONS.unitypy = _WORKER_UNITYPY


def process_bundle_candidate_worker(args: tuple[int, BundleCandidate]) -> BundleProcessResult:
    if _WORKER_OPTIONS is None:
        raise RuntimeError("bundle worker was not initialized")
    index, candidate = args
    return process_bundle_candidate(index, candidate, _WORKER_OPTIONS, _WORKER_MANIFEST_INDEX, _WORKER_UNITYPY)


def run_bundles_serial(
    selected_bundles: list[BundleCandidate],
    options: ExportOptions,
    manifest_index: ManifestIndex | None,
    unitypy: Any | None,
    progress: ProgressReporter,
) -> tuple[dict[int, BundleProcessResult], int, int, int]:
    results: dict[int, BundleProcessResult] = {}
    processed = 0
    completed_asset_rows = 0
    completed_errors = 0
    for index, candidate in enumerate(selected_bundles, start=1):
        result = process_bundle_candidate(index, candidate, options, manifest_index, unitypy)
        results[index] = result
        processed += 1
        completed_asset_rows += len(result.asset_rows)
        if result.error:
            completed_errors += 1
        progress.update(processed, completed_asset_rows, completed_errors, result.progress_label)
    return results, processed, completed_asset_rows, completed_errors


def run_bundles_parallel(
    selected_bundles: list[BundleCandidate],
    args: argparse.Namespace,
    out_root: Path,
    categories: set[str] | None,
    types: set[str] | None,
    manifest_index: ManifestIndex | None,
    progress: ProgressReporter,
) -> tuple[dict[int, BundleProcessResult], int, int, int]:
    results: dict[int, BundleProcessResult] = {}
    processed = 0
    completed_asset_rows = 0
    completed_errors = 0
    worker_options = build_export_options(args, out_root, categories, types, None)
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=init_bundle_worker,
        initargs=(worker_options, manifest_index),
    ) as executor:
        futures = [
            executor.submit(process_bundle_candidate_worker, (index, candidate))
            for index, candidate in enumerate(selected_bundles, start=1)
        ]
        for future in as_completed(futures):
            result = future.result()
            results[result.index] = result
            processed += 1
            completed_asset_rows += len(result.asset_rows)
            if result.error:
                completed_errors += 1
            progress.update(processed, completed_asset_rows, completed_errors, result.progress_label)
    return results, processed, completed_asset_rows, completed_errors


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    start_time = time.time()

    if args.workers < 1:
        parser.error("--workers must be greater than or equal to 1")

    yoo_roots = resolve_yoo_roots(args.game_root, args.yoo_root, args.source_layout)
    out_root = Path(args.out).expanduser().resolve()
    packages = parse_csv(args.packages)
    categories = parse_csv_lower(args.categories) if args.categories else None
    types = parse_csv_lower(args.types) if args.types else None

    if categories:
        unknown_categories = categories - OUTPUT_CATEGORIES
        if unknown_categories:
            parser.error(f"unknown --categories value(s): {', '.join(sorted(unknown_categories))}")

    validate_roots(yoo_roots)

    package_roots = list(iter_package_roots(yoo_roots, packages))
    package_rows = [package_report_row(yoo_root, package_root) for yoo_root, package_root in package_roots]
    if args.list_packages:
        print(json.dumps(package_rows, ensure_ascii=False, indent=2))
        return 0

    bundle_paths = list(iter_bundle_files(package_roots))
    total_bundles = len(bundle_paths)
    selected_bundles = bundle_paths[: args.limit] if args.limit else bundle_paths
    raw_file_paths = list(iter_raw_files(package_roots)) if args.copy_rawfiles else []

    manifest_index = None
    if not args.no_manifest_check:
        manifest_index = build_manifest_index(package_roots)

    unitypy = None
    if not args.no_export and args.workers == 1:
        unitypy = import_unitypy()

    options = build_export_options(args, out_root, categories, types, unitypy)
    ctx = ExportContext(options=options, used_outputs=set(), manifest_index=manifest_index)

    asset_rows: list[dict[str, Any]] = []
    bundle_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    processed = 0
    progress = ProgressReporter(len(selected_bundles), args.progress_style, args.progress_every)
    if selected_bundles and args.progress_style != "none":
        print(
            f"Processing {len(selected_bundles)} bundle(s) "
            f"from {total_bundles} discovered bundle(s). "
            f"manifest_refs={len(manifest_index.rows) if manifest_index else 'skipped'} "
            f"workers={args.workers}",
            flush=True,
        )

    results: dict[int, BundleProcessResult] = {}
    completed_asset_rows = 0
    completed_errors = 0
    if args.workers == 1:
        results, processed, completed_asset_rows, completed_errors = run_bundles_serial(
            selected_bundles, options, manifest_index, unitypy, progress
        )
    else:
        try:
            results, processed, completed_asset_rows, completed_errors = run_bundles_parallel(
                selected_bundles, args, out_root, categories, types, manifest_index, progress
            )
        except (BrokenExecutor, OSError) as exc:
            print(
                f"warning: multiprocessing unavailable ({exc.__class__.__name__}: {exc}); "
                f"falling back to a single worker",
                file=sys.stderr,
                flush=True,
            )
            if unitypy is None and not args.no_export:
                unitypy = import_unitypy()
                options.unitypy = unitypy
            progress = ProgressReporter(len(selected_bundles), args.progress_style, args.progress_every)
            results, processed, completed_asset_rows, completed_errors = run_bundles_serial(
                selected_bundles, options, manifest_index, unitypy, progress
            )
    progress.finish()

    for index in range(1, len(selected_bundles) + 1):
        result = results[index]
        if result.bundle_row is not None:
            bundle_rows.append(result.bundle_row)
        asset_rows.extend(result.asset_rows)
        if result.error:
            errors.append(result.error)

    copied_rawfiles = 0
    listed_rawfiles = 0
    skipped_rawfiles = 0
    if args.copy_rawfiles:
        for raw_file in raw_file_paths:
            if category_is_enabled("raw", options):
                target = rawfile_output_path(ctx, raw_file)
                copy_file(raw_file.data_path, target, args.execute)
                asset_rows.append(rawfile_row(raw_file, target, "copied_rawfile" if args.execute else "listed_rawfile", out_root))
                if args.execute:
                    copied_rawfiles += 1
                else:
                    listed_rawfiles += 1
            else:
                asset_rows.append(rawfile_row(raw_file, None, "skipped_category", out_root))
                skipped_rawfiles += 1

    bundle_modes = Counter(row["mode"] for row in bundle_rows)
    layout_counts = Counter(row["layout"] for row in bundle_rows)
    asset_statuses = Counter(row["status"] for row in asset_rows)
    package_counts = Counter(row["package"] for row in bundle_rows)
    duration_sec = round(time.time() - start_time, 3)
    summary = {
        "execute": args.execute,
        "duration_sec": duration_sec,
        "yoo_root": str(yoo_roots[0].path) if len(yoo_roots) == 1 else "multiple",
        "yoo_roots": [{"layout": root.layout, "path": str(root.path)} for root in yoo_roots],
        "source_layout": args.source_layout,
        "out": str(out_root),
        "packages": sorted(packages) if packages else "all",
        "categories": sorted(categories) if categories else "all",
        "types": sorted(types) if types else "all",
        "processed_bundles": processed,
        "discovered_bundles": total_bundles,
        "workers": args.workers,
        "asset_rows": len(asset_rows),
        "rawfiles_discovered": len(raw_file_paths),
        "rawfiles_listed": listed_rawfiles,
        "rawfiles_copied": copied_rawfiles,
        "rawfiles_skipped": skipped_rawfiles,
        "errors": len(errors),
        "manifest_check": "skipped" if manifest_index is None else "static_scan",
        "manifest_refs": 0 if manifest_index is None else len(manifest_index.rows),
        "bundle_modes": dict(bundle_modes),
        "layout_counts": dict(layout_counts),
        "asset_statuses": dict(asset_statuses),
        "package_counts": dict(package_counts),
        "note": "dry-run only; add --execute to write files" if not args.execute else "files written",
    }

    if args.execute:
        out_root.mkdir(parents=True, exist_ok=True)
        write_csv(out_root / "package_report.csv", PACKAGE_FIELDS, package_rows)
        write_csv(out_root / "bundles.csv", BUNDLE_FIELDS, bundle_rows)
        write_csv(out_root / "assets.csv", ASSET_FIELDS, asset_rows)
        if manifest_index is not None:
            write_csv(out_root / "manifest_refs.csv", MANIFEST_REF_FIELDS, manifest_index.rows)
        (out_root / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors and args.fail_on_error:
        return 2
    return 0
