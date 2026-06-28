from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


CJK_RE = re.compile(r"[\u3400-\u9fff]")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?$")
URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
RESOURCE_REF_RE = re.compile(
    r"(?:^|[\\/])[A-Za-z0-9_. -]+[\\/]|"
    r"\.(?:png|jpg|jpeg|webp|prefab|asset|bytes|json|wav|ogg|mp3|controller|mat|shader)$",
    re.IGNORECASE,
)
DEFAULT_TEXT_FIELD_RE = re.compile(
    r"(?:name|title|text|textid|desc|description|comment|content|message|dialog|choice|label|language|string)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TableMeta:
    rel_path: str
    table_name: str
    match_status: str
    packet_asset_name: str
    packet_asset_path: str
    row_count: str
    column_count: str


@dataclass(frozen=True)
class TextRecord:
    table_name: str
    match_status: str
    packet_asset_name: str
    packet_asset_path: str
    rel_path: str
    row_index: int
    row_id: str
    field_name: str
    text_kind: str
    text: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract searchable text rows from probe_table_bins.py tables_json output."
    )
    parser.add_argument(
        "--table-probe",
        help="Directory containing table_bins.csv and tables_json/. Use this for normal probe_table_bins.py output.",
    )
    parser.add_argument("--table-report", help="Explicit table_bins.csv path. Overrides --table-probe.")
    parser.add_argument("--tables-json", help="Explicit tables_json directory. Overrides --table-probe.")
    parser.add_argument("--out", required=True, help="Output directory for table_texts.csv and summary.json.")
    parser.add_argument("--table-regex", help="Only include tables whose name or relative path matches this regex.")
    parser.add_argument("--field-regex", help="Only include string fields matching this regex.")
    parser.add_argument("--keyword", action="append", default=[], help="Only include text containing this keyword. Repeatable.")
    parser.add_argument("--only-cjk", action="store_true", help="Only include text that contains CJK characters.")
    parser.add_argument("--all-strings", action="store_true", help="Include every non-empty string, except dates unless --include-dates is set.")
    parser.add_argument("--include-dates", action="store_true", help="Include DateTime-looking string values.")
    parser.add_argument("--export-json", action="store_true", help="Also write table_texts.json.")
    parser.add_argument("--max-records", type=int, default=0, help="Maximum records to write. 0 means no limit.")
    return parser.parse_args(argv)


def normalize_rel_path(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def load_table_meta(path: Path | None) -> dict[str, TableMeta]:
    if path is None or not path.exists():
        return {}

    metas: dict[str, TableMeta] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rel_path = normalize_rel_path(row.get("rel_path", ""))
            if not rel_path:
                continue
            metas[rel_path] = TableMeta(
                rel_path=rel_path,
                table_name=row.get("table_name", ""),
                match_status=row.get("match_status", ""),
                packet_asset_name=row.get("packet_asset_name", ""),
                packet_asset_path=row.get("packet_asset_path", ""),
                row_count=row.get("row_count", ""),
                column_count=row.get("column_count", ""),
            )
    return metas


def iter_table_json_files(root: Path) -> Iterable[tuple[str, Path]]:
    for path in sorted(item for item in root.rglob("*.json") if item.is_file()):
        rel = normalize_rel_path(str(path.relative_to(root)))
        if rel.endswith(".json"):
            rel = rel[:-5]
        yield rel, path


def pick_row_id(row: dict[str, Any]) -> str:
    for key in ("Id", "ID", "id", "EventId", "MissionId", "Key"):
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return ""


def flatten_strings(value: Any, prefix: str) -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten_strings(item, f"{prefix}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten_strings(item, child)


def classify_text(field_name: str, value: str) -> str:
    lower = field_name.lower()
    if URL_RE.match(value):
        return "url"
    if "textid" in lower or lower.endswith("_text_id"):
        return "text_id"
    if "desc" in lower or "description" in lower:
        return "description"
    if "comment" in lower:
        return "comment"
    if "title" in lower:
        return "title"
    if "name" in lower:
        return "name"
    if "choice" in lower:
        return "choice"
    if CJK_RE.search(value):
        return "cjk_text"
    if RESOURCE_REF_RE.search(value):
        return "resource_ref"
    return "string"


def should_include(
    field_name: str,
    value: str,
    args: argparse.Namespace,
    table_pattern: re.Pattern[str] | None,
    field_pattern: re.Pattern[str] | None,
    table_identity: str,
) -> bool:
    if not value:
        return False
    if not args.include_dates and DATE_RE.match(value):
        return False
    if table_pattern and not table_pattern.search(table_identity):
        return False
    if field_pattern and not field_pattern.search(field_name):
        return False
    if args.only_cjk and not CJK_RE.search(value):
        return False
    if args.keyword and not any(keyword.lower() in value.lower() for keyword in args.keyword):
        return False
    if args.all_strings or field_pattern:
        return True
    return bool(DEFAULT_TEXT_FIELD_RE.search(field_name) or CJK_RE.search(value) or URL_RE.match(value))


def extract_records(args: argparse.Namespace) -> list[TextRecord]:
    probe_root = Path(args.table_probe).resolve() if args.table_probe else None
    table_report = Path(args.table_report).resolve() if args.table_report else (probe_root / "table_bins.csv" if probe_root else None)
    tables_json = Path(args.tables_json).resolve() if args.tables_json else (probe_root / "tables_json" if probe_root else None)
    if tables_json is None:
        raise SystemExit("Either --table-probe or --tables-json is required.")
    if not tables_json.exists():
        raise SystemExit(f"tables_json directory does not exist: {tables_json}")

    metas = load_table_meta(table_report)
    table_pattern = re.compile(args.table_regex, re.IGNORECASE) if args.table_regex else None
    field_pattern = re.compile(args.field_regex, re.IGNORECASE) if args.field_regex else None
    records: list[TextRecord] = []

    for rel_path, path in iter_table_json_files(tables_json):
        meta = metas.get(rel_path, TableMeta(rel_path, "", "", "", "", "", ""))
        table_identity = " ".join(part for part in (meta.table_name, meta.packet_asset_name, meta.packet_asset_path, rel_path) if part)
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"warning: failed to read {path}: {exc}", file=sys.stderr)
            continue
        if not isinstance(rows, list):
            continue

        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            row_id = pick_row_id(row)
            for key, value in row.items():
                for field_name, text in flatten_strings(value, str(key)):
                    if not should_include(field_name, text, args, table_pattern, field_pattern, table_identity):
                        continue
                    records.append(
                        TextRecord(
                            table_name=meta.table_name,
                            match_status=meta.match_status,
                            packet_asset_name=meta.packet_asset_name,
                            packet_asset_path=meta.packet_asset_path,
                            rel_path=rel_path,
                            row_index=row_index,
                            row_id=row_id,
                            field_name=field_name,
                            text_kind=classify_text(field_name, text),
                            text=text,
                        )
                    )
                    if args.max_records and len(records) >= args.max_records:
                        return records
    return records


def write_csv(path: Path, records: list[TextRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "table_name",
        "match_status",
        "packet_asset_name",
        "packet_asset_path",
        "rel_path",
        "row_index",
        "row_id",
        "field_name",
        "text_kind",
        "text",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def main() -> int:
    args = parse_args()
    out_root = Path(args.out).resolve()
    records = extract_records(args)
    write_csv(out_root / "table_texts.csv", records)

    if args.export_json:
        (out_root / "table_texts.json").write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = {
        "records": len(records),
        "tables": len({record.rel_path for record in records}),
        "table_names": dict(Counter(record.table_name or "<unknown>" for record in records).most_common()),
        "text_kinds": dict(Counter(record.text_kind for record in records).most_common()),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
