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

    for yoo_root, package_root in package_roots:
        for manifest_path in iter_manifest_files(yoo_root, package_root):
            try:
                refs = extract_manifest_strings(manifest_path.read_bytes())
            except OSError:
                continue
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

    return ManifestIndex(rows=rows, hash_refs=hash_refs, asset_refs=tuple(sorted(asset_refs)), asset_cache={})


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
