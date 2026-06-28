from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .constants import STREAMING_MANIFEST_SUFFIXES
from .models import ManifestIndex, YooRoot
from .utils import normalize_ref, short_path


ASSET_PATH_RE = re.compile(
    r"Assets[/\\][^\x00\r\n\"'<>|]{1,240}?\."
    r"(?:png|jpg|jpeg|tga|psd|prefab|mat|fbx|anim|controller|asset|bytes|txt|json|shader|wav|ogg|mp3|acb|awb|mp4|atlas|skel)",
    re.IGNORECASE,
)
HASH_TOKEN_RE = re.compile(r"\b[a-fA-F0-9]{16,64}\b")
PRINTABLE_RUN_RE = re.compile(r"[A-Za-z0-9_./\\:@$#%+=,\- ]{4,240}")


def _read_u16(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 2 > len(data):
        raise ValueError("unexpected end while reading uint16")
    return int.from_bytes(data[offset : offset + 2], "little"), offset + 2


def _read_i32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise ValueError("unexpected end while reading int32")
    return int.from_bytes(data[offset : offset + 4], "little", signed=True), offset + 4


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    length, offset = _read_u16(data, offset)
    if offset + length > len(data):
        raise ValueError("string exceeds manifest size")
    value = data[offset : offset + length].decode("utf-8")
    return value, offset + length


def _parse_rawfile_manifest_with_mode(data: bytes, asset_record_mode: str, bundle_record_mode: str) -> dict[str, Any] | None:
    if not data.startswith(b"OOY\x00"):
        return None

    offset = 4
    try:
        file_version, offset = _read_string(data, offset)
        offset += 11
        pipeline, offset = _read_string(data, offset)
        package_name, offset = _read_string(data, offset)
        package_version, offset = _read_string(data, offset)
        build_time, offset = _read_string(data, offset)
        asset_count, offset = _read_i32(data, offset)
        if asset_count < 0 or asset_count > 1_000_000:
            return None

        assets: list[dict[str, Any]] = []
        for index in range(asset_count):
            asset_name, offset = _read_string(data, offset)
            asset_path, offset = _read_string(data, offset)
            asset_extra: dict[str, Any]
            if asset_record_mode == "fixed":
                if offset + 10 > len(data):
                    return None
                asset_flags = data[offset : offset + 10]
                offset += 10
                asset_extra = {"asset_flags_hex": asset_flags.hex(" ")}
            elif asset_record_mode == "builtin":
                if offset + 4 > len(data):
                    return None
                prefix_hex = data[offset : offset + 4].hex(" ")
                offset += 4
                location, offset = _read_string(data, offset)
                bundle_index, offset = _read_i32(data, offset)
                if offset + 2 > len(data):
                    return None
                suffix_hex = data[offset : offset + 2].hex(" ")
                offset += 2
                asset_extra = {
                    "asset_flags_hex": f"{prefix_hex} | {location} | {bundle_index} | {suffix_hex}",
                    "location": location,
                    "bundle_index": bundle_index,
                }
            else:
                raise ValueError(f"unknown asset record mode: {asset_record_mode}")
            assets.append(
                {
                    "index": index,
                    "asset_name": asset_name,
                    "asset_path": asset_path,
                    **asset_extra,
                }
            )

        bundle_count, offset = _read_i32(data, offset)
        if bundle_count < 0 or bundle_count > 1_000_000:
            return None

        bundles: list[dict[str, Any]] = []
        for index in range(bundle_count):
            bundle_name, offset = _read_string(data, offset)
            if offset + 4 > len(data):
                return None
            bundle_flags = data[offset : offset + 4]
            offset += 4
            bundle_hash, offset = _read_string(data, offset)
            checksum, offset = _read_string(data, offset)
            if bundle_record_mode == "fixed":
                if offset + 13 > len(data):
                    return None
                bundle_size = int.from_bytes(data[offset : offset + 8], "little", signed=False)
                trailer_hex = data[offset : offset + 13].hex(" ")
                offset += 13
            elif bundle_record_mode == "builtin":
                if offset + 11 > len(data):
                    return None
                bundle_size = int.from_bytes(data[offset : offset + 8], "little", signed=False)
                offset += 8
                prefix_hex = data[offset : offset + 3].hex(" ")
                offset += 3
                location, offset = _read_string(data, offset)
                if offset + 2 > len(data):
                    return None
                suffix_hex = data[offset : offset + 2].hex(" ")
                offset += 2
                trailer_hex = f"{prefix_hex} | {location} | {suffix_hex}"
            else:
                raise ValueError(f"unknown bundle record mode: {bundle_record_mode}")
            asset = assets[index] if index < len(assets) else {}
            bundles.append(
                {
                    "index": index,
                    "bundle_name": bundle_name,
                    "bundle_hash": bundle_hash,
                    "checksum": checksum,
                    "bundle_size": bundle_size,
                    "bundle_flags_hex": bundle_flags.hex(" "),
                    "trailer_hex": trailer_hex,
                    "asset_name": asset.get("asset_name", ""),
                    "asset_path": asset.get("asset_path", ""),
                }
            )
    except (UnicodeDecodeError, ValueError):
        return None

    if offset != len(data):
        return None

    return {
        "file_version": file_version,
        "pipeline": pipeline,
        "package_name": package_name,
        "package_version": package_version,
        "build_time": build_time,
        "assets": assets,
        "bundles": bundles,
    }


def parse_rawfile_manifest(data: bytes) -> dict[str, Any] | None:
    """Parse RawFileBuildPipeline YooAsset manifests used by Packet-like packages."""
    for asset_record_mode, bundle_record_mode in (("fixed", "fixed"), ("builtin", "builtin")):
        parsed = _parse_rawfile_manifest_with_mode(data, asset_record_mode, bundle_record_mode)
        if parsed:
            parsed["asset_record_mode"] = asset_record_mode
            parsed["bundle_record_mode"] = bundle_record_mode
            return parsed
    return None


def extract_manifest_strings(data: bytes) -> set[str]:
    text = data.decode("utf-8", errors="ignore")
    refs = {match.group(0).strip("\x00\r\n\t ") for match in ASSET_PATH_RE.finditer(text)}
    refs.update(match.group(0).strip("\x00\r\n\t ") for match in HASH_TOKEN_RE.finditer(text))
    for match in PRINTABLE_RUN_RE.finditer(text):
        value = match.group(0).strip("\x00\r\n\t ")
        if "/" in value or "\\" in value:
            refs.add(value)
    return {ref for ref in refs if ref}


def iter_manifest_files(yoo_root: YooRoot, package_root: Path) -> Iterable[Path]:
    if yoo_root.layout == "hot_update":
        manifest_dir = package_root / "ManifestFiles"
        if manifest_dir.exists():
            yield from sorted(p for p in manifest_dir.rglob("*") if p.is_file())
        return

    yield from sorted(
        p
        for p in package_root.rglob("*")
        if p.is_file() and p.suffix.lower() in STREAMING_MANIFEST_SUFFIXES
    )


def build_manifest_index(package_roots: Iterable[tuple[YooRoot, Path]]) -> ManifestIndex:
    rows: list[dict[str, Any]] = []
    hash_refs: set[str] = set()
    asset_refs: set[str] = set()
    hash_to_assets: dict[str, list[dict[str, Any]]] = {}

    for yoo_root, package_root in package_roots:
        for manifest_path in iter_manifest_files(yoo_root, package_root):
            try:
                manifest_bytes = manifest_path.read_bytes()
            except OSError:
                continue
            parsed_manifest = parse_rawfile_manifest(manifest_bytes)
            if parsed_manifest:
                for bundle in parsed_manifest["bundles"]:
                    bundle_hash = normalize_ref(bundle["bundle_hash"])
                    if not bundle_hash:
                        continue
                    hash_refs.add(bundle_hash)
                    asset_path = normalize_ref(bundle.get("asset_path", ""))
                    if asset_path:
                        asset_refs.add(asset_path)
                    hash_to_assets.setdefault(bundle_hash, []).append(
                        {
                            "root": str(yoo_root.path),
                            "layout": yoo_root.layout,
                            "package": package_root.name,
                            "manifest": short_path(manifest_path, package_root),
                            "asset_name": bundle.get("asset_name", ""),
                            "asset_path": bundle.get("asset_path", ""),
                            "bundle_name": bundle.get("bundle_name", ""),
                            "bundle_hash": bundle.get("bundle_hash", ""),
                            "checksum": bundle.get("checksum", ""),
                            "bundle_size": bundle.get("bundle_size", ""),
                        }
                    )
                    rows.append(
                        {
                            "root": str(yoo_root.path),
                            "layout": yoo_root.layout,
                            "package": package_root.name,
                            "manifest": short_path(manifest_path, package_root),
                            "kind": "bundle_asset",
                            "value": (
                                f"{bundle.get('bundle_hash', '')}|{bundle.get('asset_name', '')}|"
                                f"{bundle.get('asset_path', '')}"
                            ),
                        }
                    )

            refs = extract_manifest_strings(manifest_bytes)
            for ref in sorted(refs):
                normalized = normalize_ref(ref)
                kind = "hash" if HASH_TOKEN_RE.fullmatch(ref) else "asset_path" if normalized.startswith("assets/") else "text"
                if kind == "hash":
                    hash_refs.add(normalized)
                else:
                    asset_refs.add(normalized)
                rows.append(
                    {
                        "root": str(yoo_root.path),
                        "layout": yoo_root.layout,
                        "package": package_root.name,
                        "manifest": short_path(manifest_path, package_root),
                        "kind": kind,
                        "value": ref,
                    }
                )

    return ManifestIndex(
        rows=rows,
        hash_refs=hash_refs,
        asset_refs=tuple(sorted(asset_refs)),
        asset_cache={},
        hash_to_assets=hash_to_assets,
    )


def manifest_match_for_bundle(bundle_hash: str, index: ManifestIndex | None) -> tuple[str, str]:
    if index is None:
        return "not_checked", ""
    normalized = normalize_ref(bundle_hash)
    if normalized in index.hash_refs:
        return "referenced", bundle_hash
    return "not_found", ""


def manifest_match_for_asset(asset_name: str, bundle_hash: str, index: ManifestIndex | None) -> tuple[str, str]:
    if index is None:
        return "not_checked", ""
    bundle_status, bundle_match = manifest_match_for_bundle(bundle_hash, index)
    normalized_name = normalize_ref(asset_name)
    if not normalized_name:
        return bundle_status, bundle_match
    if normalized_name in index.asset_cache:
        return index.asset_cache[normalized_name]

    best = ""
    for ref in index.asset_refs:
        ref_name = ref.rsplit("/", 1)[-1]
        ref_stem = ref_name.rsplit(".", 1)[0]
        if normalized_name == ref_name or normalized_name == ref_stem or normalized_name in ref or ref_stem in normalized_name:
            best = ref
            break

    if best:
        result = ("referenced", best)
    elif bundle_status == "referenced":
        result = ("referenced_bundle", bundle_match)
    else:
        result = ("not_found", "")
    index.asset_cache[normalized_name] = result
    return result
