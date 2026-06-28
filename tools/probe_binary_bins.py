from __future__ import annotations

import argparse
import csv
import json
import re
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


ASCII_RUN_RE = re.compile(rb"[A-Za-z0-9_./:$@#%+\- ]{4,160}")
ANIMATION_HINT_RE = re.compile(
    rb"(skill_|shoot_|combat_|loop|start|choice|trial|attack|idle|move|hit|guard|rise|lock|cancel)",
    re.IGNORECASE,
)
COLLISION_HINT_RE = re.compile(rb"(collider_mesh|LevelOuterBorder|Collider_box|mesh_|boundary|trigger)", re.IGNORECASE)
ROLE_ACT_VALUES = {
    0,
    1,
    2,
    3,
    4,
    5,
    8,
    10,
    11,
    12,
    13,
    500,
    501,
    502,
    503,
    504,
    505,
    506,
    507,
    508,
    509,
    510,
    511,
    512,
    513,
    514,
    515,
    520,
    621,
    700,
}


@dataclass
class BinaryProbeResult:
    path: Path
    rel_path: str
    size: int
    category: str
    bundle_hash: str = ""
    packet_asset_name: str = ""
    packet_asset_path: str = ""
    header_hex: str = ""
    text_preview: str = ""
    strings: list[str] | None = None
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fingerprint decoded XZY .bin files that are not covered by table/string probes.")
    parser.add_argument("--input", required=True, help="Directory or single .bin file.")
    parser.add_argument("--out", required=True, help="Output directory for binary fingerprints.")
    parser.add_argument("--max-files", type=int, default=0, help="Maximum .bin files to inspect. 0 means all.")
    parser.add_argument("--sample-strings", type=int, default=30, help="Strings to include in each preview JSON.")
    parser.add_argument("--table-report", help="Optional table_bins.csv. When set, only rows whose status is not parsed are probed.")
    parser.add_argument("--game-root", help="Optional game root. Used to auto-load Packet RawFileBuildPipeline manifests.")
    parser.add_argument(
        "--packet-manifest",
        action="append",
        default=[],
        help="Optional Packet RawFileBuildPipeline manifest .bytes path. Repeat for hot-update and streaming manifests.",
    )
    return parser.parse_args()


def normalize_rel_path(value: str) -> str:
    return value.replace("/", "\\")


def load_unparsed_rel_paths(path: str | None) -> set[str]:
    if not path:
        return set()
    rel_paths: set[str] = set()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("status") != "parsed":
                rel_paths.add(normalize_rel_path(row.get("rel_path", "")))
    return rel_paths


def safe_preview_path(out_root: Path, rel_path: str) -> Path:
    return out_root / "previews" / f"{rel_path.replace('\\', '/')}.json"


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def looks_interesting_string(value: str) -> bool:
    if len(value) < 2:
        return False
    if "\x00" in value:
        return False
    controls = sum(1 for ch in value if ord(ch) < 32 and ch not in "\t\r\n")
    return controls == 0


def try_parse_string_list(data: bytes) -> tuple[bool, list[str], str]:
    offset = 0
    values: list[str] = []
    try:
        while offset < len(data):
            value, offset = read_string(data, offset)
            values.append(value)
        if values and len(values) >= 100 and all(looks_interesting_string(value) for value in values[:100]):
            return True, values, ""
        return False, values, "empty or low-quality string list"
    except Exception as exc:
        return False, values, str(exc)


def extract_ascii_runs(data: bytes, limit: int = 200) -> list[str]:
    values = [match.group(0).decode("utf-8", errors="ignore").strip() for match in ASCII_RUN_RE.finditer(data)]
    return dedupe_keep_order([value for value in values if value])[:limit]


def little_u16(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 2 > len(data):
        return None
    return int.from_bytes(data[offset : offset + 2], "little")


def little_u32(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    return int.from_bytes(data[offset : offset + 4], "little")


def has_exact_count_layout(data: bytes) -> bool:
    if not data:
        return False
    byte_count = data[0]
    if byte_count and byte_count <= 128 and (len(data) - 1) % byte_count == 0:
        width = (len(data) - 1) // byte_count
        if 4 <= width <= 64:
            return True
    int_count = little_u32(data, 0)
    if int_count and int_count <= 128 and (len(data) - 4) % int_count == 0:
        width = (len(data) - 4) // int_count
        if 4 <= width <= 96:
            return True
    return False


def looks_like_animation_state_skeleton(data: bytes, rel_path: str = "") -> bool:
    if "animationpacket" not in rel_path.replace("/", "\\").lower():
        return False
    if not data or len(data) > 4096:
        return False
    if extract_ascii_runs(data, limit=1):
        return False
    if all(byte == 0 for byte in data):
        return len(data) <= 64

    nonzero_ratio = sum(1 for byte in data if byte) / len(data)
    if nonzero_ratio > 0.35 or len(set(data)) > 64:
        return False

    if has_exact_count_layout(data):
        return True

    compact_act = little_u16(data, 1)
    aligned_count = little_u32(data, 0)
    aligned_act = little_u32(data, 4)
    if data[0] <= 64 and compact_act in ROLE_ACT_VALUES:
        return True
    if aligned_count is not None and 0 <= aligned_count <= 128 and aligned_act in ROLE_ACT_VALUES:
        return True
    return False


def classify_binary(data: bytes, rel_path: str = "") -> tuple[str, str, list[str], str]:
    if len(data) <= 4:
        return "tiny_placeholder", data.decode("utf-8", errors="replace"), [], ""

    if data.startswith(b"fileFormatVersion:"):
        text = data.decode("utf-8", errors="replace")
        strings = [line.strip() for line in text.splitlines() if line.strip()]
        return "unity_yaml_meta", text[:500], strings, ""

    ascii_head = data[:4096]
    if ANIMATION_HINT_RE.search(ascii_head):
        strings = extract_ascii_runs(data, limit=40)
        return "animation_like", "", strings, ""
    if looks_like_animation_state_skeleton(data, rel_path):
        return "animation_state_skeleton", "", [], ""
    if COLLISION_HINT_RE.search(ascii_head):
        strings = extract_ascii_runs(data, limit=40)
        return "collision_like", "", strings, ""

    ok, values, error = try_parse_string_list(data)
    if ok:
        return "string_list", "", values, ""

    ascii_runs = extract_ascii_runs(data)
    strings = ascii_runs
    if strings:
        return "binary_with_strings", "", strings, error
    return "binary_unknown", "", [], error


def probe_file(path: Path, input_root: Path, packet_manifest_map: dict[str, dict[str, Any]]) -> BinaryProbeResult:
    data = path.read_bytes()
    try:
        rel_path = str(path.relative_to(input_root))
    except ValueError:
        rel_path = path.name

    bundle_hash = bundle_hash_from_rel_path(rel_path) or bundle_hash_from_rel_path(str(path))
    manifest_match = packet_manifest_map.get(bundle_hash, {})
    packet_asset_name = str(manifest_match.get("asset_name", ""))
    packet_asset_path = str(manifest_match.get("asset_path", ""))
    category, text_preview, strings, error = classify_binary(data, rel_path)
    return BinaryProbeResult(
        path=path,
        rel_path=rel_path,
        size=len(data),
        category=category,
        bundle_hash=bundle_hash,
        packet_asset_name=packet_asset_name,
        packet_asset_path=packet_asset_path,
        header_hex=data[:32].hex(" "),
        text_preview=text_preview,
        strings=strings,
        error=error,
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
        "category",
        "string_count",
        "first_strings",
        "header_hex",
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
    unparsed_rel_paths = load_unparsed_rel_paths(args.table_report)

    files = list(iter_bin_files(input_root))
    if unparsed_rel_paths:
        files = [
            path
            for path in files
            if normalize_rel_path(str(path.relative_to(rel_root))) in unparsed_rel_paths
        ]
    if args.max_files:
        files = files[: args.max_files]

    results = [probe_file(path, rel_root, packet_manifest_map) for path in files]
    rows = []
    for result in results:
        entry_index, file_id_hex = entry_metadata(result.rel_path)
        strings = result.strings or []
        rows.append(
            {
                "rel_path": result.rel_path,
                "entry_index": entry_index,
                "file_id_hex": file_id_hex,
                "bundle_hash": result.bundle_hash,
                "packet_asset_name": result.packet_asset_name,
                "packet_asset_path": result.packet_asset_path,
                "size": result.size,
                "category": result.category,
                "string_count": len(strings),
                "first_strings": " | ".join(strings[:5]),
                "header_hex": result.header_hex,
                "error": result.error,
            }
        )

        preview_path = safe_preview_path(out_root, result.rel_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_payload = {
            "rel_path": result.rel_path,
            "bundle_hash": result.bundle_hash,
            "packet_asset_name": result.packet_asset_name,
            "packet_asset_path": result.packet_asset_path,
            "size": result.size,
            "category": result.category,
            "header_hex": result.header_hex,
            "text_preview": result.text_preview,
            "strings": strings[: args.sample_strings],
            "error": result.error,
        }
        preview_path.write_text(json.dumps(preview_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csv(out_root / "binary_bins.csv", rows)
    summary = {
        "input": str(input_root),
        "out": str(out_root),
        "files": len(results),
        "categories": {},
        "packet_manifest_bundles": len(packet_manifest_map),
    }
    for result in results:
        summary["categories"][result.category] = summary["categories"].get(result.category, 0) + 1
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
