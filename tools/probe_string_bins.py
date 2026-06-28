from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from probe_table_bins import (  # noqa: E402
    bundle_hash_from_rel_path,
    entry_metadata,
    iter_bin_files,
    iter_game_packet_manifests,
    load_packet_manifest_map,
    read_string,
)


@dataclass
class StringParseResult:
    path: Path
    rel_path: str
    size: int
    status: str
    bundle_hash: str = ""
    packet_asset_name: str = ""
    packet_asset_path: str = ""
    string_count: int = 0
    consumed: int = 0
    error: str = ""
    strings: list[str] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe decoded XZY .bin files for 7-bit length-prefixed UTF-8 strings.")
    parser.add_argument("--input", required=True, help="Directory or single .bin file.")
    parser.add_argument("--out", required=True, help="Output directory for string reports.")
    parser.add_argument("--max-files", type=int, default=0, help="Maximum .bin files to inspect. 0 means all.")
    parser.add_argument("--sample-strings", type=int, default=20, help="Strings to include in each preview JSON.")
    parser.add_argument("--export-json", action="store_true", help="Write full parsed string lists to strings_json/.")
    parser.add_argument("--game-root", help="Optional game root. Used to auto-load Packet RawFileBuildPipeline manifests.")
    parser.add_argument(
        "--packet-manifest",
        action="append",
        default=[],
        help="Optional Packet RawFileBuildPipeline manifest .bytes path. Repeat for hot-update and streaming manifests.",
    )
    parser.add_argument(
        "--only-packet-assets",
        default="",
        help="Comma-separated Packet manifest asset names to keep, for example Languages. Empty means all.",
    )
    return parser.parse_args()


def selected_asset_names(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def safe_preview_path(out_root: Path, rel_path: str) -> Path:
    return out_root / "previews" / f"{rel_path.replace('\\', '/')}.json"


def safe_strings_path(out_root: Path, rel_path: str) -> Path:
    return out_root / "strings_json" / f"{rel_path.replace('\\', '/')}.json"


def parse_string_file(path: Path, input_root: Path, packet_manifest_map: dict[str, dict[str, Any]]) -> StringParseResult:
    data = path.read_bytes()
    try:
        rel_path = str(path.relative_to(input_root))
    except ValueError:
        rel_path = path.name

    bundle_hash = bundle_hash_from_rel_path(rel_path) or bundle_hash_from_rel_path(str(path))
    manifest_match = packet_manifest_map.get(bundle_hash, {})
    packet_asset_name = str(manifest_match.get("asset_name", ""))
    packet_asset_path = str(manifest_match.get("asset_path", ""))

    try:
        offset = 0
        values: list[str] = []
        while offset < len(data):
            value, offset = read_string(data, offset)
            values.append(value)
        if not values:
            raise ValueError("empty string list")
        return StringParseResult(
            path=path,
            rel_path=rel_path,
            size=len(data),
            status="parsed",
            bundle_hash=bundle_hash,
            packet_asset_name=packet_asset_name,
            packet_asset_path=packet_asset_path,
            string_count=len(values),
            consumed=offset,
            strings=values,
        )
    except Exception as exc:
        return StringParseResult(
            path=path,
            rel_path=rel_path,
            size=len(data),
            status="not_string_list",
            bundle_hash=bundle_hash,
            packet_asset_name=packet_asset_name,
            packet_asset_path=packet_asset_path,
            error=str(exc),
        )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rel_path",
        "entry_index",
        "file_id_hex",
        "bundle_hash",
        "packet_asset_name",
        "packet_asset_path",
        "size",
        "status",
        "string_count",
        "consumed",
        "error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    input_root = Path(args.input).resolve()
    out_root = Path(args.out).resolve()
    rel_root = input_root.parent if input_root.is_file() else input_root

    manifest_paths = [Path(path) for path in args.packet_manifest]
    if args.game_root:
        manifest_paths.extend(iter_game_packet_manifests(Path(args.game_root)))
    packet_manifest_map = load_packet_manifest_map(manifest_paths)
    allowed_assets = selected_asset_names(args.only_packet_assets)

    files = list(iter_bin_files(input_root))
    if allowed_assets:
        files = [
            path
            for path in files
            if packet_manifest_map.get(bundle_hash_from_rel_path(str(path)), {}).get("asset_name") in allowed_assets
        ]
    if args.max_files:
        files = files[: args.max_files]

    results = [parse_string_file(path, rel_root, packet_manifest_map) for path in files]
    rows = []
    for result in results:
        entry_index, file_id_hex = entry_metadata(result.rel_path)
        rows.append(
            {
                "rel_path": result.rel_path,
                "entry_index": entry_index,
                "file_id_hex": file_id_hex,
                "bundle_hash": result.bundle_hash,
                "packet_asset_name": result.packet_asset_name,
                "packet_asset_path": result.packet_asset_path,
                "size": result.size,
                "status": result.status,
                "string_count": result.string_count,
                "consumed": result.consumed,
                "error": result.error,
            }
        )
        if result.status != "parsed" or result.strings is None:
            continue

        preview_path = safe_preview_path(out_root, result.rel_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_payload = {
            "rel_path": result.rel_path,
            "bundle_hash": result.bundle_hash,
            "packet_asset_name": result.packet_asset_name,
            "packet_asset_path": result.packet_asset_path,
            "string_count": result.string_count,
            "strings": result.strings[: args.sample_strings],
        }
        preview_path.write_text(json.dumps(preview_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        if args.export_json:
            strings_path = safe_strings_path(out_root, result.rel_path)
            strings_path.parent.mkdir(parents=True, exist_ok=True)
            payload = [{"index": index, "text": value} for index, value in enumerate(result.strings)]
            strings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csv(out_root / "string_bins.csv", rows)
    summary = {
        "input": str(input_root),
        "out": str(out_root),
        "files": len(results),
        "parsed": sum(1 for result in results if result.status == "parsed"),
        "not_string_list": sum(1 for result in results if result.status != "parsed"),
        "export_json": bool(args.export_json),
        "packet_manifest_bundles": len(packet_manifest_map),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
