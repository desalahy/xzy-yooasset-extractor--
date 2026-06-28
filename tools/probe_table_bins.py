from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


TYPE_RE = re.compile(
    r"^(?:byte|ushort|u?int|u?long|float|double|bool|string|DateTime|"
    r"byte\[\]|ushort\[\]|u?int\[\]|u?long\[\]|float\[\]|double\[\]|bool\[\]|string\[\]|DateTime\[\]|"
    r"enum:[A-Za-z0-9_]+)$"
)
ENTRY_NAME_RE = re.compile(r"^(?P<index>\d{5})_(?P<file_id>[0-9a-fA-F]{8})\.bin$")
BUNDLE_HASH_RE = re.compile(r"(?i)(?:^|[\\/])(?P<hash>[0-9a-f]{32})(?:[\\/]|$)")
DUMP_STRUCT_RE = re.compile(r"^public struct (?P<name>[A-Za-z0-9_]+)\.tData\b")
DUMP_FIELD_RE = re.compile(r"^\s*public (?P<type>[A-Za-z0-9_<>,\[\].]+) (?P<name>[A-Za-z_][A-Za-z0-9_]*);")
BUILTIN_TYPES = {"byte", "ushort", "uint", "int", "long", "ulong", "float", "double", "bool", "string", "DateTime"}


@dataclass(frozen=True)
class DumpField:
    name: str
    type_name: str
    schema_type: str


@dataclass(frozen=True)
class DumpTable:
    name: str
    fields: tuple[DumpField, ...]
    signature: str


@dataclass(frozen=True)
class TableMatch:
    status: str
    table_name: str = ""
    field_names: tuple[str, ...] = ()
    candidate_tables: tuple[str, ...] = ()


@dataclass
class ParseResult:
    path: Path
    rel_path: str
    size: int
    status: str
    bundle_hash: str = ""
    packet_asset_name: str = ""
    packet_asset_path: str = ""
    row_count: int = 0
    column_count: int = 0
    types: list[str] | None = None
    consumed: int = 0
    error: str = ""
    table_name: str = ""
    match_status: str = ""
    candidate_tables: list[str] | None = None
    field_names: list[str] | None = None
    rows: list[dict[str, Any]] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe decoded XZY Packet .bin files for the columnar table format.")
    parser.add_argument("--input", required=True, help="Directory or single .bin file.")
    parser.add_argument("--out", required=True, help="Output directory for table reports.")
    parser.add_argument("--max-files", type=int, default=0, help="Maximum .bin files to inspect. 0 means all.")
    parser.add_argument("--sample-rows", type=int, default=5, help="Rows to include in each preview JSON.")
    parser.add_argument("--export-json", action="store_true", help="Write full parsed rows to tables_json/.")
    parser.add_argument("--dump-cs", help="Optional Il2CppDumper dump.cs. Used to map table schemas to field names.")
    parser.add_argument("--game-root", help="Optional game root. Used to auto-load Packet RawFileBuildPipeline manifests.")
    parser.add_argument(
        "--packet-manifest",
        action="append",
        default=[],
        help="Optional Packet RawFileBuildPipeline manifest .bytes path. Repeat for hot-update and streaming manifests.",
    )
    return parser.parse_args()


def iter_bin_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        if path.suffix.lower() == ".bin":
            yield path
        return
    yield from sorted(item for item in path.rglob("*.bin") if item.is_file())


def iter_game_packet_manifests(game_root: Path) -> Iterable[Path]:
    data_root = game_root / "XzyLauncher_Data"
    streaming_packet = data_root / "StreamingAssets" / "yoo" / "Packet"
    hot_packet = data_root / "yoo" / "Packet" / "ManifestFiles"
    if streaming_packet.exists():
        yield from sorted(path for path in streaming_packet.glob("*.bytes") if path.is_file())
    if hot_packet.exists():
        yield from sorted(path for path in hot_packet.glob("*.bytes") if path.is_file())


def load_packet_manifest_map(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    try:
        from xzy_yooasset_core.manifest import parse_rawfile_manifest
    except ImportError:
        return {}

    mapping: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            parsed = parse_rawfile_manifest(path.read_bytes())
        except OSError:
            continue
        if not parsed or parsed.get("package_name") != "Packet":
            continue
        for bundle in parsed.get("bundles", []):
            bundle_hash = str(bundle.get("bundle_hash", "")).lower()
            if not bundle_hash:
                continue
            mapping[bundle_hash] = {
                "asset_name": bundle.get("asset_name", ""),
                "asset_path": bundle.get("asset_path", ""),
                "manifest": str(path),
            }
    return mapping


def bundle_hash_from_rel_path(rel_path: str) -> str:
    match = BUNDLE_HASH_RE.search(rel_path)
    return match.group("hash").lower() if match else ""


def normalize_dump_type(type_name: str) -> str:
    if type_name.startswith("System."):
        type_name = type_name.removeprefix("System.")
    if type_name.endswith("[]"):
        return f"{normalize_dump_type(type_name[:-2])}[]"
    if type_name in BUILTIN_TYPES:
        return type_name
    return f"enum:{type_name}"


def parse_dump_tables(path: Path) -> list[DumpTable]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    tables: list[DumpTable] = []
    index = 0
    while index < len(lines):
        match = DUMP_STRUCT_RE.match(lines[index])
        if not match:
            index += 1
            continue

        table_name = match.group("name")
        fields: list[DumpField] = []
        brace_depth = 0
        started = False
        index += 1

        while index < len(lines):
            line = lines[index]
            if "{" in line:
                brace_depth += line.count("{")
                started = True
            if "}" in line:
                brace_depth -= line.count("}")

            field_match = DUMP_FIELD_RE.match(line)
            if field_match:
                type_name = field_match.group("type")
                fields.append(
                    DumpField(
                        name=field_match.group("name"),
                        type_name=type_name,
                        schema_type=normalize_dump_type(type_name),
                    )
                )

            index += 1
            if started and brace_depth <= 0:
                break

        if fields:
            signature = "|".join(field.schema_type for field in fields)
            tables.append(DumpTable(name=table_name, fields=tuple(fields), signature=signature))
    return tables


def build_dump_signature_index(path: str | None) -> dict[str, list[DumpTable]]:
    if not path:
        return {}
    tables = parse_dump_tables(Path(path))
    index: dict[str, list[DumpTable]] = defaultdict(list)
    for table in tables:
        index[table.signature].append(table)
    return dict(index)


def filter_candidates_for_packet(candidates: list[DumpTable], packet_asset_name: str) -> list[DumpTable]:
    if packet_asset_name == "GameTables":
        filtered = [table for table in candidates if not table.name.startswith("UiTable")]
        return filtered or candidates
    if packet_asset_name == "UiTables":
        filtered = [table for table in candidates if table.name.startswith("UiTable")]
        return filtered or candidates
    return candidates


def unique_field_names(fields: tuple[DumpField, ...]) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    names: list[str] = []
    for index, field in enumerate(fields):
        counts[field.name] += 1
        if counts[field.name] == 1:
            names.append(field.name)
        else:
            names.append(f"{field.name}_{index:02d}")
    return tuple(names)


def match_dump_table(types: list[str], packet_asset_name: str, signature_index: dict[str, list[DumpTable]]) -> TableMatch:
    if not signature_index:
        return TableMatch("not_checked")

    signature = "|".join(types)
    candidates = signature_index.get(signature, [])
    if not candidates:
        return TableMatch("no_match")

    candidate_names = tuple(table.name for table in candidates)
    if len(candidates) == 1:
        table = candidates[0]
        return TableMatch("unique_signature", table.name, unique_field_names(table.fields), candidate_names)

    filtered = filter_candidates_for_packet(candidates, packet_asset_name)
    if len(filtered) == 1:
        table = filtered[0]
        return TableMatch("package_preferred", table.name, unique_field_names(table.fields), candidate_names)
    if len(filtered) < len(candidates):
        return TableMatch("package_ambiguous", candidate_tables=tuple(table.name for table in filtered))
    return TableMatch("ambiguous_signature", candidate_tables=candidate_names)


def read_7bit_int(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(5):
        if offset >= len(data):
            raise ValueError("unexpected end while reading 7-bit integer")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return value, offset
        shift += 7
    raise ValueError("7-bit integer is too long")


def read_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset >= len(data):
        raise ValueError("unexpected end while reading string length")
    length, offset = read_7bit_int(data, offset)
    if offset + length > len(data):
        raise ValueError("string exceeds file size")
    value = data[offset : offset + length].decode("utf-8")
    return value, offset + length


def parse_schema(data: bytes) -> tuple[int, int, list[str], int]:
    if len(data) < 8:
        raise ValueError("too small for table header")
    row_count, column_count = struct.unpack_from("<ii", data, 0)
    if row_count < 0 or row_count > 2_000_000:
        raise ValueError(f"row_count out of range: {row_count}")
    if column_count <= 0 or column_count > 256:
        raise ValueError(f"column_count out of range: {column_count}")

    offset = 8
    types: list[str] = []
    for _ in range(column_count):
        type_name, offset = read_string(data, offset)
        if not TYPE_RE.fullmatch(type_name):
            raise ValueError(f"unsupported column type: {type_name!r}")
        types.append(type_name)
    return row_count, column_count, types, offset


def read_scalar(data: bytes, offset: int, type_name: str) -> tuple[Any, int]:
    if type_name == "uint" or type_name.startswith("enum:"):
        if offset + 4 > len(data):
            raise ValueError("unexpected end while reading uint")
        return struct.unpack_from("<I", data, offset)[0], offset + 4
    if type_name == "byte":
        if offset >= len(data):
            raise ValueError("unexpected end while reading byte")
        return data[offset], offset + 1
    if type_name == "ushort":
        if offset + 2 > len(data):
            raise ValueError("unexpected end while reading ushort")
        return struct.unpack_from("<H", data, offset)[0], offset + 2
    if type_name == "int":
        if offset + 4 > len(data):
            raise ValueError("unexpected end while reading int")
        return struct.unpack_from("<i", data, offset)[0], offset + 4
    if type_name == "long":
        if offset + 8 > len(data):
            raise ValueError("unexpected end while reading long")
        return struct.unpack_from("<q", data, offset)[0], offset + 8
    if type_name == "ulong":
        if offset + 8 > len(data):
            raise ValueError("unexpected end while reading ulong")
        return struct.unpack_from("<Q", data, offset)[0], offset + 8
    if type_name == "float":
        if offset + 4 > len(data):
            raise ValueError("unexpected end while reading float")
        value = struct.unpack_from("<f", data, offset)[0]
        if not math.isfinite(value):
            value = None
        return value, offset + 4
    if type_name == "double":
        if offset + 8 > len(data):
            raise ValueError("unexpected end while reading double")
        value = struct.unpack_from("<d", data, offset)[0]
        if not math.isfinite(value):
            value = None
        return value, offset + 8
    if type_name == "bool":
        if offset >= len(data):
            raise ValueError("unexpected end while reading bool")
        return bool(data[offset]), offset + 1
    if type_name == "string" or type_name == "DateTime":
        return read_string(data, offset)
    raise ValueError(f"unsupported scalar type: {type_name}")


def read_array(data: bytes, offset: int, item_type: str) -> tuple[list[Any], int]:
    if offset + 4 > len(data):
        raise ValueError("unexpected end while reading array length")
    count = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if count < 0 or count > 1_000_000:
        raise ValueError(f"array length out of range: {count}")
    values = []
    for _ in range(count):
        value, offset = read_scalar(data, offset, item_type)
        values.append(value)
    return values, offset


def read_value(data: bytes, offset: int, type_name: str) -> tuple[Any, int]:
    if type_name.endswith("[]"):
        return read_array(data, offset, type_name[:-2])
    return read_scalar(data, offset, type_name)


def column_name(index: int, type_name: str) -> str:
    clean = type_name.replace(":", "_").replace("[]", "_array")
    return f"col_{index:02d}_{clean}"


def parse_table(
    path: Path,
    input_root: Path,
    signature_index: dict[str, list[DumpTable]],
    packet_manifest_map: dict[str, dict[str, Any]],
) -> ParseResult:
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
        row_count, column_count, types, offset = parse_schema(data)
        table_match = match_dump_table(types, packet_asset_name, signature_index)
        columns: list[list[Any]] = []
        for type_name in types:
            column = []
            for _ in range(row_count):
                value, offset = read_value(data, offset, type_name)
                column.append(value)
            columns.append(column)
        if offset != len(data):
            raise ValueError(f"trailing bytes: {len(data) - offset}")

        names = list(table_match.field_names) if table_match.field_names else [
            column_name(index, type_name) for index, type_name in enumerate(types)
        ]
        rows = [
            {name: columns[column_index][row_index] for column_index, name in enumerate(names)}
            for row_index in range(row_count)
        ]
        return ParseResult(
            path=path,
            rel_path=rel_path,
            size=len(data),
            status="parsed",
            bundle_hash=bundle_hash,
            packet_asset_name=packet_asset_name,
            packet_asset_path=packet_asset_path,
            row_count=row_count,
            column_count=column_count,
            types=types,
            consumed=offset,
            table_name=table_match.table_name,
            match_status=table_match.status,
            candidate_tables=list(table_match.candidate_tables),
            field_names=names,
            rows=rows,
        )
    except Exception as exc:
        return ParseResult(
            path=path,
            rel_path=rel_path,
            size=len(data),
            status="not_table",
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
        "row_count",
        "column_count",
        "types",
        "consumed",
        "table_name",
        "match_status",
        "field_names",
        "candidate_tables",
        "error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_preview_path(out_root: Path, rel_path: str) -> Path:
    normalized = rel_path.replace("\\", "/")
    return out_root / "previews" / f"{normalized}.json"


def safe_table_path(out_root: Path, rel_path: str) -> Path:
    normalized = rel_path.replace("\\", "/")
    return out_root / "tables_json" / f"{normalized}.json"


def entry_metadata(rel_path: str) -> tuple[str, str]:
    match = ENTRY_NAME_RE.fullmatch(Path(rel_path).name)
    if not match:
        return "", ""
    return match.group("index"), match.group("file_id").lower()


def main() -> int:
    args = parse_args()
    input_root = Path(args.input).resolve()
    out_root = Path(args.out).resolve()
    rel_root = input_root.parent if input_root.is_file() else input_root

    manifest_paths = [Path(path) for path in args.packet_manifest]
    if args.game_root:
        manifest_paths.extend(iter_game_packet_manifests(Path(args.game_root)))
    packet_manifest_map = load_packet_manifest_map(manifest_paths)
    signature_index = build_dump_signature_index(args.dump_cs)

    files = list(iter_bin_files(input_root))
    if args.max_files:
        files = files[: args.max_files]

    results = [parse_table(path, rel_root, signature_index, packet_manifest_map) for path in files]

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
                "row_count": result.row_count,
                "column_count": result.column_count,
                "types": "|".join(result.types or []),
                "consumed": result.consumed,
                "table_name": result.table_name,
                "match_status": result.match_status,
                "field_names": "|".join(result.field_names or []),
                "candidate_tables": "|".join(result.candidate_tables or []),
                "error": result.error,
            }
        )
        if result.status != "parsed" or result.rows is None:
            continue

        preview_path = safe_preview_path(out_root, result.rel_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_payload = {
            "rel_path": result.rel_path,
            "bundle_hash": result.bundle_hash,
            "packet_asset_name": result.packet_asset_name,
            "packet_asset_path": result.packet_asset_path,
            "table_name": result.table_name,
            "match_status": result.match_status,
            "candidate_tables": result.candidate_tables,
            "row_count": result.row_count,
            "column_count": result.column_count,
            "types": result.types,
            "field_names": result.field_names,
            "rows": result.rows[: args.sample_rows],
        }
        preview_path.write_text(json.dumps(preview_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        if args.export_json:
            table_path = safe_table_path(out_root, result.rel_path)
            table_path.parent.mkdir(parents=True, exist_ok=True)
            table_path.write_text(json.dumps(result.rows, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csv(out_root / "table_bins.csv", rows)
    summary = {
        "input": str(input_root),
        "out": str(out_root),
        "files": len(results),
        "parsed": sum(1 for result in results if result.status == "parsed"),
        "not_table": sum(1 for result in results if result.status != "parsed"),
        "export_json": bool(args.export_json),
        "dump_tables": sum(len(tables) for tables in signature_index.values()),
        "packet_manifest_bundles": len(packet_manifest_map),
        "match_status": dict(Counter(result.match_status for result in results if result.status == "parsed")),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
