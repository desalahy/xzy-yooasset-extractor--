from __future__ import annotations

from xzy_yooasset_core.bundle import classify_bundle, is_unity_bundle, read_bundle_probe, xor_with_key, xor_with_tail_key
from xzy_yooasset_core.cli import build_parser, main
from xzy_yooasset_core.constants import ASSET_FIELDS, BUNDLE_FIELDS, MANIFEST_REF_FIELDS, OUTPUT_CATEGORIES, PACKAGE_FIELDS
from xzy_yooasset_core.discovery import (
    detect_yoo_layout,
    iter_bundle_files as _iter_bundle_files,
    iter_package_roots as _iter_package_roots,
    iter_raw_files as _iter_raw_files,
    package_report_row,
    resolve_yoo_roots,
)
from xzy_yooasset_core.exporter import (
    category_for_type,
    category_is_enabled,
    export_filter_status,
    export_object,
    import_unitypy,
    load_unity_env,
    rawfile_output_path,
    rawfile_row,
    reserve_output_path,
    row_for,
)
from xzy_yooasset_core.manifest import (
    build_manifest_index as _build_manifest_index,
    extract_manifest_strings,
    iter_manifest_files,
    manifest_match_for_asset,
    manifest_match_for_bundle,
)
from xzy_yooasset_core.models import BundleCandidate, BundleInput, ExportContext, ExportOptions, ManifestIndex, RawFileCandidate, YooRoot
from xzy_yooasset_core.progress import ProgressReporter
from xzy_yooasset_core.utils import format_duration, normalize_ref, parse_csv, parse_csv_lower, safe_name, short_path, write_csv


def iter_package_roots(yoo_roots, packages):
    return _iter_package_roots(yoo_roots, packages)


def iter_bundle_files(yoo_roots, packages):
    return _iter_bundle_files(_iter_package_roots(yoo_roots, packages))


def iter_raw_files(yoo_roots, packages):
    return _iter_raw_files(_iter_package_roots(yoo_roots, packages))


def build_manifest_index(yoo_roots, packages):
    return _build_manifest_index(_iter_package_roots(yoo_roots, packages))


__all__ = [
    "ASSET_FIELDS",
    "BUNDLE_FIELDS",
    "MANIFEST_REF_FIELDS",
    "OUTPUT_CATEGORIES",
    "PACKAGE_FIELDS",
    "BundleCandidate",
    "BundleInput",
    "ExportContext",
    "ExportOptions",
    "ManifestIndex",
    "ProgressReporter",
    "RawFileCandidate",
    "YooRoot",
    "build_manifest_index",
    "build_parser",
    "category_for_type",
    "category_is_enabled",
    "classify_bundle",
    "detect_yoo_layout",
    "export_filter_status",
    "export_object",
    "extract_manifest_strings",
    "format_duration",
    "import_unitypy",
    "is_unity_bundle",
    "iter_bundle_files",
    "iter_manifest_files",
    "iter_package_roots",
    "iter_raw_files",
    "load_unity_env",
    "main",
    "manifest_match_for_asset",
    "manifest_match_for_bundle",
    "normalize_ref",
    "package_report_row",
    "parse_csv",
    "parse_csv_lower",
    "rawfile_output_path",
    "rawfile_row",
    "read_bundle_probe",
    "reserve_output_path",
    "resolve_yoo_roots",
    "row_for",
    "safe_name",
    "short_path",
    "write_csv",
    "xor_with_key",
    "xor_with_tail_key",
]


if __name__ == "__main__":
    raise SystemExit(main())
