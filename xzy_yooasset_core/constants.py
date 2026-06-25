from __future__ import annotations


UNITY_MAGICS = (b"UnityFS", b"UnityRaw", b"UnityWeb")

OUTPUT_CATEGORIES = {
    "ui",
    "bgm",
    "audio",
    "models",
    "effects",
    "animation",
    "prefabs",
    "text",
    "textures",
    "materials",
    "raw",
    "other",
}

ASSET_FIELDS = [
    "layout",
    "package",
    "bundle_hash",
    "bundle_mode",
    "source",
    "type",
    "path_id",
    "asset_name",
    "category",
    "output",
    "status",
    "manifest_reference",
    "manifest_match",
]

BUNDLE_FIELDS = [
    "layout",
    "package",
    "bundle_hash",
    "mode",
    "source",
    "length",
    "raw_head",
    "decoded_head",
    "manifest_reference",
    "manifest_match",
]

PACKAGE_FIELDS = [
    "root",
    "layout",
    "package",
    "has_bundle_files",
    "bundle_count",
    "bundle_file_count",
    "streaming_bundle_count",
    "rawfile_count",
    "manifest_file_count",
    "manifest_bytes",
    "total_files",
    "total_bytes",
]

MANIFEST_REF_FIELDS = [
    "root",
    "layout",
    "package",
    "manifest",
    "kind",
    "value",
]

STREAMING_MANIFEST_SUFFIXES = {".bytes", ".json", ".hash", ".version"}
