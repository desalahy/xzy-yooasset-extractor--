from __future__ import annotations

import os
from pathlib import Path

from .constants import UNITY_MAGICS
from .models import BundleInput


def is_unity_bundle(data: bytes) -> bool:
    return any(data.startswith(magic) for magic in UNITY_MAGICS)


def xor_with_key(data: bytes, key: bytes, offset: int = 0) -> bytes:
    if not key:
        return data
    key_len = len(key)
    return bytes(byte ^ key[(offset + index) % key_len] for index, byte in enumerate(data))


def xor_with_tail_key(blob: bytes) -> bytes | None:
    if len(blob) <= 16:
        return None
    key = blob[-16:]
    data = blob[:-16]
    return xor_with_key(data, key)


def read_bundle_probe(path: Path) -> tuple[int, bytes, bytes, bytes]:
    with path.open("rb") as file:
        raw_head = file.read(64)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        if size <= 16:
            return size, raw_head, b"", b""
        file.seek(size - 16)
        key = file.read(16)
        data_head_len = min(64, size - 16)
        file.seek(0)
        encrypted_head = file.read(data_head_len)
    return size, raw_head, key, xor_with_key(encrypted_head, key)


def classify_bundle(
    path: Path,
    package_root: Path,
    layout: str = "hot_update",
    hash_name: str | None = None,
    load_bytes: bool = True,
) -> BundleInput:
    _size, raw_head, key, decoded_head = read_bundle_probe(path)
    package = package_root.name
    bundle_hash = hash_name or path.parent.name

    if is_unity_bundle(raw_head):
        unity_bytes = path.read_bytes() if load_bytes else None
        return BundleInput(layout, package, bundle_hash, path, "plain_unityfs", unity_bytes, raw_head, b"")

    if decoded_head and is_unity_bundle(decoded_head):
        decoded = xor_with_tail_key(path.read_bytes()) if load_bytes else None
        return BundleInput(layout, package, bundle_hash, path, "tail16_xor_unityfs", decoded, raw_head, decoded_head)
    if key:
        raw_bytes = path.read_bytes() if load_bytes else None
        return BundleInput(layout, package, bundle_hash, path, "non_unity_raw", raw_bytes, raw_head, decoded_head)
    return BundleInput(layout, package, bundle_hash, path, "unknown", None, raw_head, b"")
