from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import sys
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from xzy_yooasset_core.discovery import iter_package_roots, resolve_yoo_roots
from xzy_yooasset_core.manifest import build_manifest_index
from xzy_yooasset_core.models import ManifestIndex
from xzy_yooasset_core.utils import normalize_ref, safe_name


ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
TRAILING_DIGITS_RE = re.compile(r"\d+$")

MAGICS = [
    (b"UnityFS", "unityfs"),
    (b"PK\x03\x04", "zip"),
    (b"\x1f\x8b", "gzip"),
    (b"\x04\x22\x4d\x18", "lz4_frame"),
    (b"MZ", "pe"),
    (b"CPMV", "cpmv"),
    (b"{", "json_candidate"),
    (b"[", "json_array_candidate"),
]


@dataclass
class PacketEntry:
    rel_path: str
    index: int
    file_id: int
    encrypted: bool
    origin_length: int
    stored_length: int
    record_offset: int
    data_offset: int
    end_offset: int
    head_hex: str
    magic: str
    entropy_4k: float
    printable_ratio_4k: float
    string_sample: str
    extract_status: str = ""
    output: str = ""
    decoded_magic: str = ""
    decode_status: str = ""


@dataclass
class PacketProbe:
    path: Path
    rel_path: str
    size: int
    sha256: str
    valid: bool
    encrypted: bool
    count: int
    consumed: int
    remaining: int
    total_stored_bytes: int
    total_origin_bytes: int
    first_error: str
    entries: list[PacketEntry]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe XZY Packet/BattlePacket/Assembly/AnimationPacket raw .bin files. "
            "The expected format is: bool encrypted, int32 count, then repeated file records."
        )
    )
    parser.add_argument("--input", required=True, help="Directory or single .bin file to probe.")
    parser.add_argument("--out", required=True, help="Directory for packet reports.")
    parser.add_argument("--game-root", default="", help="Optional game root. When provided, Packet manifests are scanned to map bundle hashes to packet names.")
    parser.add_argument("--yoo-root", default="", help="Optional direct YooAssets root used for manifest lookup.")
    parser.add_argument("--source-layout", choices=("all", "hot", "streaming"), default="all", help="YooAssets source layout for manifest lookup.")
    parser.add_argument("--packages", default="Assembly,BattlePacket,Packet,AnimationPacket", help="Comma-separated package names used for manifest lookup.")
    parser.add_argument("--max-files", type=int, default=0, help="Maximum packet files to inspect. 0 means all.")
    parser.add_argument("--sample-entries", type=int, default=20, help="Maximum per-packet entries written into packet JSON previews.")
    parser.add_argument(
        "--extract",
        action="store_true",
        help=(
            "Extract internal payloads. Encrypted payloads are decoded when an AES key is supplied "
            "and an IV can be derived from manifest lookup, --packet-name, or --iv-hex."
        ),
    )
    parser.add_argument("--key-text", default="", help="AES key as UTF-8 text. GameConfig._EncryptKey is stored in this form for the researched build.")
    parser.add_argument("--key-hex", default="", help="AES key as hex.")
    parser.add_argument("--iv-hex", default="", help="Fixed AES IV as hex. Mostly useful for one-off experiments.")
    parser.add_argument("--packet-name", default="", help="Fixed Packet logical name used to derive IV. Mostly useful when probing one packet file.")
    parser.add_argument("--strict-decode", action="store_true", help="Only write decrypted output when the decoded payload looks valid.")
    return parser.parse_args()


def iter_input_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in (".bin", ".rawfile"):
            yield item


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def i32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    total = len(data)
    counts = Counter(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    printable = sum(1 for value in data if value in (9, 10, 13) or 32 <= value <= 126)
    return printable / len(data)


def classify_magic(data: bytes) -> str:
    for signature, label in MAGICS:
        if data.startswith(signature):
            return label
    if data.startswith((b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")):
        return "zlib_candidate"
    return "unknown"


def is_valid_pe(data: bytes) -> bool:
    if len(data) < 0x100 or not data.startswith(b"MZ"):
        return False
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    return 0 < e_lfanew < len(data) - 4 and data[e_lfanew : e_lfanew + 4] == b"PE\x00\x00"


def decoded_score(data: bytes) -> int:
    if not data:
        return 0
    if is_valid_pe(data):
        return 100
    stripped = data.lstrip()
    if stripped.startswith((b"{", b"[")):
        return 90
    if data.startswith(b"CPMV"):
        return 80
    magic = classify_magic(data)
    if magic != "unknown":
        return 70
    ratio = printable_ratio(data[: min(4096, len(data))])
    if ratio >= 0.85:
        return 50
    return 0


def extract_string_sample(data: bytes, limit: int = 5) -> str:
    values = []
    for match in ASCII_RE.finditer(data):
        text = match.group(0).decode("utf-8", errors="replace")
        values.append(text.replace("\r", "\\r").replace("\n", "\\n"))
        if len(values) >= limit:
            break
    return " | ".join(values)


def parse_csv(value: str) -> set[str] | None:
    items = {part.strip() for part in value.split(",") if part.strip()}
    return items or None


def key_from_args(args: argparse.Namespace) -> bytes | None:
    if args.key_hex:
        try:
            return bytes.fromhex(args.key_hex)
        except ValueError as exc:
            raise SystemExit(f"invalid --key-hex: {exc}") from exc
    if args.key_text:
        return args.key_text.encode("utf-8")
    return None


def fixed_iv_from_args(args: argparse.Namespace) -> bytes | None:
    if args.iv_hex:
        try:
            iv = bytes.fromhex(args.iv_hex)
        except ValueError as exc:
            raise SystemExit(f"invalid --iv-hex: {exc}") from exc
        if len(iv) != 16:
            raise SystemExit("--iv-hex must decode to exactly 16 bytes")
        return iv
    return None


def iv_from_name(name: str) -> bytes:
    iv = bytearray(16)
    iv[: min(16, len(name.encode("utf-8")))] = name.encode("utf-8")[:16]
    return bytes(iv)


def base_packet_name(asset_name: str, asset_path: str) -> str:
    path_name = Path(asset_path.replace("\\", "/")).name if asset_path else ""
    if path_name:
        stem = path_name.rsplit(".", 1)[0]
        ext = "." + path_name.rsplit(".", 1)[1] if "." in path_name else ""
    else:
        stem = asset_name.rsplit(".", 1)[0]
        ext = "." + asset_name.rsplit(".", 1)[1] if "." in asset_name else ".p"
    if "." not in stem:
        stem = TRAILING_DIGITS_RE.sub("", stem)
    return f"{stem}{ext or '.p'}"


def packet_name_candidates(asset_info: dict[str, object] | None, fixed_packet_name: str) -> list[str]:
    names: list[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in names:
            names.append(value)

    add(fixed_packet_name)
    if asset_info:
        asset_name = str(asset_info.get("asset_name", ""))
        asset_path = str(asset_info.get("asset_path", ""))
        add(base_packet_name(asset_name, asset_path))
        if asset_path:
            add(Path(asset_path.replace("\\", "/")).name)
            add(Path(asset_path.replace("\\", "/")).stem)
        add(asset_name)
    return names


def best_manifest_asset(probe: PacketProbe, manifest_index: ManifestIndex | None) -> dict[str, object] | None:
    if manifest_index is None:
        return None
    matches = manifest_index.hash_to_assets.get(normalize_ref(Path(probe.rel_path).stem), [])
    if not matches:
        return None
    for match in matches:
        if str(match.get("package", "")).lower() == Path(probe.rel_path).parts[-2].lower():
            return match
    return matches[0]


def build_manifest_lookup(args: argparse.Namespace) -> ManifestIndex | None:
    if not args.game_root and not args.yoo_root:
        return None
    yoo_roots = resolve_yoo_roots(args.game_root, args.yoo_root, args.source_layout)
    if not yoo_roots:
        return None
    package_roots = list(iter_package_roots(yoo_roots, parse_csv(args.packages)))
    return build_manifest_index(package_roots)


def make_entry(
    data: bytes,
    rel_path: str,
    index: int,
    file_id: int,
    encrypted: bool,
    origin_length: int,
    stored_length: int,
    record_offset: int,
    data_offset: int,
) -> PacketEntry:
    end_offset = data_offset + stored_length
    sample = data[data_offset : min(end_offset, data_offset + 4096)]
    return PacketEntry(
        rel_path=rel_path,
        index=index,
        file_id=file_id,
        encrypted=encrypted,
        origin_length=origin_length,
        stored_length=stored_length,
        record_offset=record_offset,
        data_offset=data_offset,
        end_offset=end_offset,
        head_hex=data[data_offset : min(end_offset, data_offset + 32)].hex(" "),
        magic=classify_magic(sample),
        entropy_4k=round(entropy(sample), 4),
        printable_ratio_4k=round(printable_ratio(sample), 4),
        string_sample=extract_string_sample(sample),
    )


def parse_packet(path: Path, root: Path) -> PacketProbe:
    data = path.read_bytes()
    size = len(data)
    rel_path = path.relative_to(root).as_posix() if path != root and root.is_dir() else path.name
    file_hash = sha256_file(path)

    if size < 5:
        return PacketProbe(path, rel_path, size, file_hash, False, False, 0, 0, size, 0, 0, "too small for packet header", [])

    encrypted_flag = data[0]
    if encrypted_flag not in (0, 1):
        return PacketProbe(path, rel_path, size, file_hash, False, False, 0, 0, size, 0, 0, f"unexpected encrypted flag: {encrypted_flag}", [])

    encrypted = encrypted_flag == 1
    count = i32(data, 1)
    if count < 0 or count > 1_000_000:
        return PacketProbe(path, rel_path, size, file_hash, False, encrypted, count, 5, size - 5, 0, 0, f"unreasonable file count: {count}", [])

    cursor = 5
    entries: list[PacketEntry] = []
    first_error = ""
    for index in range(count):
        record_offset = cursor
        try:
            if encrypted:
                if cursor + 12 > size:
                    raise ValueError("record header exceeds file size")
                file_id = u32(data, cursor)
                origin_length = i32(data, cursor + 4)
                stored_length = i32(data, cursor + 8)
                data_offset = cursor + 12
            else:
                if cursor + 8 > size:
                    raise ValueError("record header exceeds file size")
                file_id = u32(data, cursor)
                stored_length = i32(data, cursor + 4)
                origin_length = stored_length
                data_offset = cursor + 8

            if origin_length < 0:
                raise ValueError(f"negative origin length: {origin_length}")
            if stored_length < 0:
                raise ValueError(f"negative stored length: {stored_length}")
            if data_offset + stored_length > size:
                raise ValueError(
                    f"payload exceeds file size: data_offset={data_offset} length={stored_length} size={size}"
                )
            if encrypted and stored_length % 16 != 0:
                raise ValueError(f"encrypted stored length is not AES-block aligned: {stored_length}")
            if encrypted and stored_length < origin_length:
                raise ValueError(f"encrypted stored length is smaller than origin length: {stored_length} < {origin_length}")
            if encrypted and stored_length - origin_length > 16:
                raise ValueError(f"encrypted padding gap is larger than one AES block: {stored_length - origin_length}")

            entry = make_entry(data, rel_path, index, file_id, encrypted, origin_length, stored_length, record_offset, data_offset)
            entries.append(entry)
            cursor = data_offset + stored_length
        except ValueError as exc:
            first_error = f"entry {index}: {exc}"
            break

    remaining = size - cursor
    valid = not first_error and len(entries) == count and remaining == 0
    if not first_error and remaining != 0:
        first_error = f"trailing bytes after parsed entries: {remaining}"

    return PacketProbe(
        path=path,
        rel_path=rel_path,
        size=size,
        sha256=file_hash,
        valid=valid,
        encrypted=encrypted,
        count=count,
        consumed=cursor,
        remaining=remaining,
        total_stored_bytes=sum(entry.stored_length for entry in entries),
        total_origin_bytes=sum(entry.origin_length for entry in entries),
        first_error=first_error,
        entries=entries,
    )


def try_aes(payload: bytes, key: bytes, iv: bytes) -> bytes | None:
    try:
        from Crypto.Cipher import AES  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            f"pycryptodome is required for AES decode. Run: uv sync, then use uv run python ... "
            f"Original import error: {type(exc).__name__}: {exc}"
        ) from exc

    if len(key) not in (16, 24, 32):
        raise RuntimeError(f"AES key must be 16, 24, or 32 bytes; got {len(key)}")
    if len(iv) != 16:
        raise RuntimeError(f"AES IV must be 16 bytes; got {len(iv)}")
    return AES.new(key, AES.MODE_CBC, iv).decrypt(payload)


def decode_variants(data: bytes) -> Iterable[tuple[bytes, str]]:
    yield data, "decoded_aes"
    for label, kwargs in (
        ("zlib", {}),
        ("deflate_raw", {"wbits": -15}),
        ("gzip", {"wbits": 31}),
    ):
        try:
            yield zlib.decompress(data, **kwargs), f"decoded_aes_{label}"
        except Exception:
            pass


def try_decrypt_payload(
    payload: bytes,
    origin_length: int,
    key: bytes | None,
    iv_candidates: list[tuple[str, bytes]],
) -> tuple[bytes | None, str, str]:
    if not key:
        return None, "encrypted_no_key", ""
    if not iv_candidates:
        return None, "encrypted_no_iv", ""

    best_data: bytes | None = None
    best_status = ""
    best_iv_name = ""
    best_score = -1
    first_error = ""
    for iv_name, iv in iv_candidates:
        try:
            decrypted = try_aes(payload, key, iv)[:origin_length]
            for decoded, status in decode_variants(decrypted):
                score = decoded_score(decoded)
                if score > best_score:
                    best_data = decoded
                    best_status = f"{status}:iv={iv_name}:score={score}"
                    best_iv_name = iv_name
                    best_score = score
        except Exception as exc:
            if not first_error:
                first_error = f"aes_failed:{type(exc).__name__}:{exc}"
    if best_data is None:
        return None, first_error or "aes_failed", ""
    return best_data, best_status, best_iv_name


def output_name(entry: PacketEntry, suffix: str) -> str:
    return f"{entry.index:05d}_{entry.file_id:08x}{suffix}"


def decoded_output_suffix(data: bytes) -> str:
    stripped = data.lstrip()
    if stripped.startswith((b"{", b"[")):
        return ".json"
    if is_valid_pe(data):
        return ".dll"
    if data.startswith(b"CPMV"):
        return ".cpmv"
    return ".bin"


def extract_entries(
    probe: PacketProbe,
    input_root: Path,
    out_root: Path,
    key: bytes | None,
    iv_candidates: list[tuple[str, bytes]],
    strict_decode: bool,
) -> None:
    data = probe.path.read_bytes()
    packet_dir = out_root / "extracted" / Path(probe.rel_path).with_suffix("")
    packet_dir.mkdir(parents=True, exist_ok=True)

    for entry in probe.entries:
        payload = data[entry.data_offset : entry.end_offset]
        if entry.encrypted:
            decoded, status, _iv_name = try_decrypt_payload(payload, entry.origin_length, key, iv_candidates)
            score = decoded_score(decoded or b"")
            if decoded is None or (strict_decode and score <= 0):
                target = packet_dir / output_name(entry, ".encrypted")
                target.write_bytes(payload)
                entry.extract_status = status
                entry.output = str(target.relative_to(out_root))
            else:
                target = packet_dir / output_name(entry, decoded_output_suffix(decoded))
                target.write_bytes(decoded)
                entry.extract_status = status
                entry.decoded_magic = classify_magic(decoded)
                entry.decode_status = status
                entry.output = str(target.relative_to(out_root))
        else:
            suffix = ".json" if payload.lstrip().startswith((b"{", b"[")) else ".bin"
            target = packet_dir / output_name(entry, suffix)
            target.write_bytes(payload)
            entry.extract_status = "extracted_plain"
            entry.output = str(target.relative_to(out_root))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def packet_row(probe: PacketProbe) -> dict[str, object]:
    lengths = [entry.stored_length for entry in probe.entries]
    origin_lengths = [entry.origin_length for entry in probe.entries]
    return {
        "rel_path": probe.rel_path,
        "size": probe.size,
        "sha256": probe.sha256,
        "valid": probe.valid,
        "encrypted": probe.encrypted,
        "count": probe.count,
        "parsed_entries": len(probe.entries),
        "consumed": probe.consumed,
        "remaining": probe.remaining,
        "total_stored_bytes": probe.total_stored_bytes,
        "total_origin_bytes": probe.total_origin_bytes,
        "min_stored_length": min(lengths) if lengths else "",
        "max_stored_length": max(lengths) if lengths else "",
        "min_origin_length": min(origin_lengths) if origin_lengths else "",
        "max_origin_length": max(origin_lengths) if origin_lengths else "",
        "first_entry_id": f"{probe.entries[0].file_id:08x}" if probe.entries else "",
        "first_error": probe.first_error,
        "path": str(probe.path),
    }


def entry_row(entry: PacketEntry) -> dict[str, object]:
    return {
        "rel_path": entry.rel_path,
        "index": entry.index,
        "file_id_dec": entry.file_id,
        "file_id_hex": f"{entry.file_id:08x}",
        "encrypted": entry.encrypted,
        "origin_length": entry.origin_length,
        "stored_length": entry.stored_length,
        "record_offset": entry.record_offset,
        "data_offset": entry.data_offset,
        "end_offset": entry.end_offset,
        "head_hex": entry.head_hex,
        "magic": entry.magic,
        "entropy_4k": entry.entropy_4k,
        "printable_ratio_4k": entry.printable_ratio_4k,
        "string_sample": entry.string_sample,
        "extract_status": entry.extract_status,
        "output": entry.output,
        "decoded_magic": entry.decoded_magic,
        "decode_status": entry.decode_status,
    }


def write_packet_previews(out_root: Path, probes: list[PacketProbe], sample_entries: int) -> None:
    preview_root = out_root / "packet_previews"
    preview_root.mkdir(parents=True, exist_ok=True)
    for probe in probes:
        preview = packet_row(probe)
        preview["entries"] = [entry_row(entry) for entry in probe.entries[:sample_entries]]
        safe_name = probe.rel_path.replace("/", "__").replace("\\", "__").replace(":", "_")
        (preview_root / f"{safe_name}.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    input_root = input_path if input_path.is_dir() else input_path.parent
    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    key = key_from_args(args)
    fixed_iv = fixed_iv_from_args(args)
    manifest_index = build_manifest_lookup(args)

    files = sorted(iter_input_files(input_path))
    if args.max_files:
        files = files[: args.max_files]

    probes = [parse_packet(path, input_root) for path in files]
    if args.extract:
        for probe in probes:
            if probe.valid:
                asset_info = best_manifest_asset(probe, manifest_index)
                candidates = []
                if fixed_iv:
                    candidates.append(("fixed", fixed_iv))
                for packet_name in packet_name_candidates(asset_info, args.packet_name):
                    candidates.append((packet_name, iv_from_name(packet_name)))
                extract_entries(probe, input_root, out_root, key, candidates, args.strict_decode)

    packet_rows = [packet_row(probe) for probe in probes]
    entry_rows = [entry_row(entry) for probe in probes for entry in probe.entries]

    write_csv(
        out_root / "packets.csv",
        [
            "rel_path",
            "size",
            "sha256",
            "valid",
            "encrypted",
            "count",
            "parsed_entries",
            "consumed",
            "remaining",
            "total_stored_bytes",
            "total_origin_bytes",
            "min_stored_length",
            "max_stored_length",
            "min_origin_length",
            "max_origin_length",
            "first_entry_id",
            "first_error",
            "path",
        ],
        packet_rows,
    )
    write_csv(
        out_root / "packet_entries.csv",
        [
            "rel_path",
            "index",
            "file_id_dec",
            "file_id_hex",
            "encrypted",
            "origin_length",
            "stored_length",
            "record_offset",
            "data_offset",
            "end_offset",
            "head_hex",
            "magic",
            "entropy_4k",
            "printable_ratio_4k",
            "string_sample",
            "extract_status",
            "output",
            "decoded_magic",
            "decode_status",
        ],
        entry_rows,
    )
    write_packet_previews(out_root, probes, args.sample_entries)

    summary = {
        "input": str(input_path),
        "out": str(out_root),
        "packets": len(probes),
        "valid_packets": sum(1 for probe in probes if probe.valid),
        "encrypted_packets": sum(1 for probe in probes if probe.valid and probe.encrypted),
        "plain_packets": sum(1 for probe in probes if probe.valid and not probe.encrypted),
        "entries": len(entry_rows),
        "stored_bytes": sum(probe.total_stored_bytes for probe in probes),
        "origin_bytes": sum(probe.total_origin_bytes for probe in probes),
        "entry_magic": dict(Counter(entry.magic for probe in probes for entry in probe.entries)),
        "extract": bool(args.extract),
        "decode_key_supplied": bool(key),
        "aes_key_supplied": bool(key),
        "manifest_lookup": "enabled" if manifest_index is not None else "disabled",
        "manifest_hash_mappings": len(manifest_index.hash_to_assets) if manifest_index is not None else 0,
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
