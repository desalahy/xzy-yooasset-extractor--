from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


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
    "package",
    "has_bundle_files",
    "bundle_count",
    "manifest_file_count",
    "manifest_bytes",
    "total_files",
    "total_bytes",
]

MANIFEST_REF_FIELDS = [
    "package",
    "manifest",
    "kind",
    "value",
]

ASSET_PATH_RE = re.compile(
    r"Assets[/\\][^\x00\r\n\"'<>|]{1,240}?\."
    r"(?:png|jpg|jpeg|tga|psd|prefab|mat|fbx|anim|controller|asset|bytes|txt|json|shader|wav|ogg|mp3|acb|awb|mp4|atlas|skel)",
    re.IGNORECASE,
)
HASH_TOKEN_RE = re.compile(r"\b[a-fA-F0-9]{16,64}\b")
PRINTABLE_RUN_RE = re.compile(r"[A-Za-z0-9_./\\:@$#%+=,\- ]{4,240}")


@dataclass
class BundleInput:
    package: str
    hash_name: str
    source_path: Path
    mode: str
    unity_bytes: bytes | None
    raw_head: bytes
    decoded_head: bytes


@dataclass
class ExportOptions:
    out_root: Path
    execute: bool
    keep_bundles: bool
    no_export: bool
    categories: set[str] | None
    types: set[str] | None
    ui_packages: set[str]
    model_packages: set[str]
    effects_packages: set[str]
    animation_packages: set[str]
    unitypy: Any | None = None


@dataclass
class ExportContext:
    options: ExportOptions
    used_outputs: set[Path]
    manifest_index: ManifestIndex | None = None


@dataclass
class ManifestIndex:
    rows: list[dict[str, Any]]
    hash_refs: set[str]
    asset_refs: tuple[str, ...]
    asset_cache: dict[str, tuple[str, str]]


class ProgressReporter:
    def __init__(self, total: int, style: str, every: int) -> None:
        self.total = max(total, 0)
        self.style = "none" if every <= 0 else style
        self.every = max(every, 0)
        self.start_time = time.time()
        self.last_len = 0

    def update(self, processed: int, asset_count: int, error_count: int, current: str = "", force: bool = False) -> None:
        if self.style == "none" or self.total <= 0:
            return
        if not force and self.every and processed % self.every != 0 and processed != self.total:
            return

        elapsed = time.time() - self.start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (self.total - processed) / rate if rate > 0 else 0
        percent = (processed / self.total) * 100 if self.total else 100

        if self.style == "lines":
            print(
                f"[progress] {processed}/{self.total} {percent:5.1f}% "
                f"assets={asset_count} errors={error_count} "
                f"elapsed={format_duration(elapsed)} eta={format_duration(remaining)} {current}",
                flush=True,
            )
            return

        width = 28
        filled = int(width * processed / self.total) if self.total else width
        bar = "#" * filled + "-" * (width - filled)
        message = (
            f"\r[{bar}] {processed}/{self.total} {percent:5.1f}% "
            f"assets={asset_count} errors={error_count} "
            f"elapsed={format_duration(elapsed)} eta={format_duration(remaining)} {current}"
        )
        padding = " " * max(0, self.last_len - len(message))
        print(message + padding, end="", flush=True)
        self.last_len = len(message)

    def finish(self) -> None:
        if self.style == "bar" and self.last_len:
            print()


def parse_csv(value: str | None) -> set[str] | None:
    if not value:
        return None
    items = {part.strip() for part in value.split(",") if part.strip()}
    return items or None


def parse_csv_lower(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def safe_name(value: str, fallback: str = "unnamed", max_len: int = 96) -> str:
    value = value.replace("\\", "/").split("/")[-1]
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value).strip(" .")
    if not value:
        value = fallback
    return value[:max_len]


def normalize_ref(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def short_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def is_unity_bundle(data: bytes) -> bool:
    return any(data.startswith(magic) for magic in UNITY_MAGICS)


def xor_with_tail_key(blob: bytes) -> bytes | None:
    if len(blob) <= 16:
        return None
    key = blob[-16:]
    data = blob[:-16]
    return bytes(data[i] ^ key[i % 16] for i in range(len(data)))


def extract_manifest_strings(data: bytes) -> set[str]:
    text = data.decode("utf-8", errors="ignore")
    refs = {match.group(0).strip("\x00\r\n\t ") for match in ASSET_PATH_RE.finditer(text)}
    refs.update(match.group(0).strip("\x00\r\n\t ") for match in HASH_TOKEN_RE.finditer(text))
    for match in PRINTABLE_RUN_RE.finditer(text):
        value = match.group(0).strip("\x00\r\n\t ")
        if "/" in value or "\\" in value:
            refs.add(value)
    return {ref for ref in refs if ref}


def build_manifest_index(yoo_root: Path, packages: set[str] | None) -> ManifestIndex:
    rows: list[dict[str, Any]] = []
    hash_refs: set[str] = set()
    asset_refs: set[str] = set()

    for package_root in iter_package_roots(yoo_root, packages):
        manifest_dir = package_root / "ManifestFiles"
        if not manifest_dir.exists():
            continue
        for manifest_path in sorted(p for p in manifest_dir.rglob("*") if p.is_file()):
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


def import_unitypy(deps_dir: str | None) -> Any:
    env_deps = os.environ.get("UNITYPY_DEPS_DIR")
    chosen_deps = deps_dir or env_deps
    if chosen_deps:
        deps_path = Path(chosen_deps).expanduser().resolve()
        if not deps_path.exists():
            raise RuntimeError(f"dependency directory does not exist: {deps_path}")
        sys.path.insert(0, str(deps_path))

    try:
        module = importlib.import_module("UnityPy")
    except ImportError as exc:
        raise RuntimeError(
            "UnityPy is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    has_loader = callable(getattr(module, "load", None)) or callable(getattr(module, "Environment", None))
    if not has_loader:
        raise RuntimeError(
            "Imported a UnityPy module without load/Environment. "
            f"module_file={getattr(module, '__file__', None)!r}. "
            "Check PYTHONPATH, --deps-dir, or reinstall UnityPy."
        )
    return module


def load_unity_env(unitypy: Any, data: bytes) -> Any:
    loader = getattr(unitypy, "load", None)
    if callable(loader):
        return loader(data)
    env_cls = getattr(unitypy, "Environment", None)
    if callable(env_cls):
        return env_cls(data)
    raise RuntimeError("UnityPy loader is unavailable")


def resolve_yoo_root(game_root: str, yoo_root: str) -> Path:
    if yoo_root:
        return Path(yoo_root).expanduser().resolve()
    if not game_root:
        raise SystemExit("Provide --game-root or --yoo-root.")

    root = Path(game_root).expanduser().resolve()
    if root.name.lower() == "yoo":
        return root

    candidate = root / "XzyLauncher_Data" / "yoo"
    if candidate.exists():
        return candidate
    return candidate


def iter_package_roots(yoo_root: Path, packages: set[str] | None) -> Iterable[Path]:
    for package_root in sorted(p for p in yoo_root.iterdir() if p.is_dir()):
        if packages and package_root.name not in packages:
            continue
        yield package_root


def iter_bundle_files(yoo_root: Path, packages: set[str] | None) -> Iterable[tuple[Path, Path]]:
    for package_root in iter_package_roots(yoo_root, packages):
        bundle_dir = package_root / "BundleFiles"
        if not bundle_dir.exists():
            continue
        for data_path in sorted(bundle_dir.rglob("__data")):
            if data_path.is_file():
                yield package_root, data_path


def package_report_row(package_root: Path) -> dict[str, Any]:
    bundle_dir = package_root / "BundleFiles"
    manifest_dir = package_root / "ManifestFiles"
    bundle_count = 0
    if bundle_dir.exists():
        bundle_count = sum(1 for p in bundle_dir.rglob("__data") if p.is_file())

    manifest_files = []
    if manifest_dir.exists():
        manifest_files = [p for p in manifest_dir.rglob("*") if p.is_file()]

    all_files = [p for p in package_root.rglob("*") if p.is_file()]
    return {
        "package": package_root.name,
        "has_bundle_files": bundle_dir.exists(),
        "bundle_count": bundle_count,
        "manifest_file_count": len(manifest_files),
        "manifest_bytes": sum(p.stat().st_size for p in manifest_files),
        "total_files": len(all_files),
        "total_bytes": sum(p.stat().st_size for p in all_files),
    }


def classify_bundle(path: Path, package_root: Path) -> BundleInput:
    blob = path.read_bytes()
    raw_head = blob[:64]
    package = package_root.name
    hash_name = path.parent.name

    if is_unity_bundle(blob):
        return BundleInput(package, hash_name, path, "plain_unityfs", blob, raw_head, b"")

    decoded = xor_with_tail_key(blob)
    if decoded and is_unity_bundle(decoded):
        return BundleInput(package, hash_name, path, "tail16_xor_unityfs", decoded, raw_head, decoded[:64])
    if decoded:
        return BundleInput(package, hash_name, path, "tail16_xor_non_unity", decoded, raw_head, decoded[:64])
    return BundleInput(package, hash_name, path, "unknown", None, raw_head, b"")


def category_for_type(type_name: str, asset_name: str, package: str, options: ExportOptions) -> str:
    tn = type_name.lower()
    name = asset_name.lower()
    package_l = package.lower()

    if tn in ("texture2d", "sprite") and (
        package_l in options.ui_packages or any(key in name for key in ("icon", "ui", "atlas"))
    ):
        return "ui"
    if package_l == "bgm":
        return "bgm"
    if package_l in ("voice", "se"):
        return "audio"
    if tn == "audioclip":
        if any(key in name for key in ("bgm", "music", "theme")):
            return "bgm"
        return "audio"
    if tn in ("texture2d", "sprite"):
        return "textures"
    if tn == "mesh":
        return "models"
    if tn == "material":
        return "materials"
    if tn in ("particlesystem", "particlesystemrenderer", "visualeffect", "vfxrenderer", "trailrenderer", "linerenderer"):
        return "effects"
    if any(key in name for key in ("effect", "effects", "vfx", "fx", "particle")):
        return "effects"
    if tn in ("animationclip", "animatorcontroller", "runtimeanimatorcontroller", "animator", "avatar"):
        return "animation"
    if tn in ("gameobject", "transform", "recttransform", "monobehaviour", "canvasrenderer"):
        return "prefabs"
    if package_l in options.ui_packages and package_l not in options.animation_packages:
        return "ui"
    if package_l in options.effects_packages:
        return "effects"
    if package_l in options.model_packages:
        return "models"
    if package_l in options.animation_packages:
        return "animation"
    if tn in ("textasset", "monoscript", "shader"):
        return "text"
    return "other"


def export_filter_status(category: str, type_name: str, options: ExportOptions) -> str:
    if options.categories and category not in options.categories:
        return "skipped_category"
    if options.types and type_name.lower() not in options.types:
        return "skipped_type"
    return ""


def category_is_enabled(category: str, options: ExportOptions) -> bool:
    return not options.categories or category in options.categories


def reserve_output_path(ctx: ExportContext, path: Path) -> Path:
    if path not in ctx.used_outputs:
        ctx.used_outputs.add(path)
        return path

    stem = path.stem
    suffix = path.suffix
    for index in range(1, 100000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if candidate not in ctx.used_outputs:
            ctx.used_outputs.add(candidate)
            return candidate
    raise RuntimeError(f"cannot allocate output path for {path}")


def object_output_path(ctx: ExportContext, bundle: BundleInput, category: str, type_name: str, asset_name: str, path_id: Any, ext: str) -> Path:
    clean_name = safe_name(asset_name, f"{type_name}_{path_id}")
    clean_type = safe_name(type_name, "asset", 32)
    clean_path_id = safe_name(str(path_id), "0", 48)
    filename = f"{clean_name}__{clean_type}_{clean_path_id}{ext}"
    target = ctx.options.out_root / "assets" / category / bundle.package / bundle.hash_name / filename
    return reserve_output_path(ctx, target)


def write_bytes(path: Path, data: bytes, execute: bool) -> None:
    if not execute:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def row_for(
    bundle: BundleInput,
    obj: Any,
    type_name: str,
    asset_name: str,
    category: str,
    target: Path | str | None,
    status: str,
    out_root: Path,
    manifest_index: ManifestIndex | None = None,
) -> dict[str, Any]:
    output = ""
    if target:
        target_path = Path(target)
        try:
            output = str(target_path.relative_to(out_root))
        except ValueError:
            output = str(target_path)
    manifest_reference, manifest_match = manifest_match_for_asset(asset_name, bundle.hash_name, manifest_index)

    return {
        "package": bundle.package,
        "bundle_hash": bundle.hash_name,
        "bundle_mode": bundle.mode,
        "source": str(bundle.source_path),
        "type": type_name,
        "path_id": getattr(obj, "path_id", ""),
        "asset_name": asset_name,
        "category": category,
        "output": output,
        "status": status,
        "manifest_reference": manifest_reference,
        "manifest_match": manifest_match,
    }


def normalize_raw(raw: Any) -> bytes | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, str):
        return raw.encode("utf-8", errors="replace")
    if isinstance(raw, (dict, list, tuple)):
        return json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8")
    return None


def export_object(obj: Any, bundle: BundleInput, ctx: ExportContext) -> list[dict[str, Any]]:
    options = ctx.options
    out_root = options.out_root
    try:
        data = obj.read()
        type_name = obj.type.name
        path_id = getattr(obj, "path_id", "")
        asset_name = getattr(data, "name", "") or f"{type_name}_{path_id}"
        category = category_for_type(type_name, asset_name, bundle.package, options)
        skip_status = export_filter_status(category, type_name, options)
        if skip_status:
            return [row_for(bundle, obj, type_name, asset_name, category, None, skip_status, out_root, ctx.manifest_index)]

        if type_name == "Texture2D":
            try:
                image = data.image
                if image is not None:
                    target = object_output_path(ctx, bundle, category, type_name, asset_name, path_id, ".png")
                    if options.execute:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        image.save(target)
                    return [row_for(bundle, obj, type_name, asset_name, category, target, "exported_png", out_root, ctx.manifest_index)]
            except Exception as exc:
                return [row_for(bundle, obj, type_name, asset_name, category, None, f"texture_failed:{exc}", out_root, ctx.manifest_index)]

        if type_name == "Sprite":
            try:
                image = data.image
                if image is not None:
                    target = object_output_path(ctx, bundle, category, type_name, asset_name, path_id, ".png")
                    if options.execute:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        image.save(target)
                    return [row_for(bundle, obj, type_name, asset_name, category, target, "exported_sprite_png", out_root, ctx.manifest_index)]
            except Exception as exc:
                return [row_for(bundle, obj, type_name, asset_name, category, None, f"sprite_failed:{exc}", out_root, ctx.manifest_index)]

        if type_name == "AudioClip":
            rows = []
            samples = getattr(data, "samples", None)
            if samples:
                for sample_name, sample_data in samples.items():
                    ext = Path(sample_name).suffix or ".bin"
                    sample_asset_name = Path(sample_name).stem or asset_name
                    target = object_output_path(ctx, bundle, category, type_name, sample_asset_name, path_id, ext)
                    write_bytes(target, sample_data, options.execute)
                    rows.append(row_for(bundle, obj, type_name, asset_name, category, target, "exported_audio_sample", out_root, ctx.manifest_index))
            if rows:
                return rows

        raw = None
        try:
            raw = normalize_raw(data.save())
        except Exception:
            raw = None

        if raw:
            ext = ".txt" if type_name in ("TextAsset", "MonoScript", "Shader") else ".bin"
            target = object_output_path(ctx, bundle, category, type_name, asset_name, path_id, ext)
            write_bytes(target, raw, options.execute)
            return [row_for(bundle, obj, type_name, asset_name, category, target, "exported_raw", out_root, ctx.manifest_index)]

        return [row_for(bundle, obj, type_name, asset_name, category, None, "listed_only", out_root, ctx.manifest_index)]
    except Exception as exc:
        type_name = getattr(getattr(obj, "type", None), "name", "Unknown")
        return [row_for(bundle, obj, type_name, "", "", None, f"object_failed:{exc}", ctx.options.out_root, ctx.manifest_index)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decrypt and export local YooAssets/Unity asset bundles that use a tail-16 XOR key.",
    )
    parser.add_argument("--game-root", default="", help="Game root containing XzyLauncher_Data/yoo.")
    parser.add_argument("--yoo-root", default="", help="Direct path to the YooAssets root. Overrides --game-root.")
    parser.add_argument("--out", default="xzy_assets_out", help="Output directory.")
    parser.add_argument("--packages", default="", help="Comma-separated package names, for example Icon,Main,Spine.")
    parser.add_argument("--categories", default="", help="Comma-separated output categories to export, for example ui,bgm,models,effects. Empty means all categories.")
    parser.add_argument("--types", default="", help="Comma-separated Unity object type names to export, for example Texture2D,Sprite,AudioClip. Empty means all types.")
    parser.add_argument("--limit", type=int, default=30, help="Maximum bundles to process. Use 0 for all.")
    parser.add_argument("--execute", action="store_true", help="Write exported files and index files. Without this, run as dry-run.")
    parser.add_argument("--no-export", action="store_true", help="Classify/decrypt bundles only; skip UnityPy object export.")
    parser.add_argument("--keep-bundles", action="store_true", help="Write decrypted UnityFS bundles under decrypted_bundles/.")
    parser.add_argument("--deps-dir", default="", help="Optional directory containing installed Python dependencies, such as UnityPy.")
    parser.add_argument("--progress-every", type=int, default=25, help="Print progress every N processed bundles. Use 0 to disable.")
    parser.add_argument("--progress-style", choices=("bar", "lines", "none"), default="bar", help="Progress display style. Use lines for log files.")
    parser.add_argument("--no-manifest-check", action="store_true", help="Skip ManifestFiles static reference scan.")
    parser.add_argument("--list-packages", action="store_true", help="Print package report and exit.")
    parser.add_argument("--fail-on-error", action="store_true", help="Return exit code 2 when bundle-level errors are found.")
    parser.add_argument("--ui-packages", default="Icon,Background,Main,Spine", help="Packages whose Texture2D/Sprite outputs should be grouped under assets/ui.")
    parser.add_argument("--model-packages", default="CharacterMesh,Art3D", help="Packages grouped under assets/models.")
    parser.add_argument("--effects-packages", default="BattlePacket,Effect,Effects,Vfx,VFX,Fx", help="Packages grouped under assets/effects.")
    parser.add_argument(
        "--animation-packages",
        default="Spine,AnimationPacket,CharacterTimeline,CharacterController,CharacterPerformance",
        help="Packages grouped under assets/animation for non-image objects.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    start_time = time.time()

    yoo_root = resolve_yoo_root(args.game_root, args.yoo_root)
    out_root = Path(args.out).expanduser().resolve()
    packages = parse_csv(args.packages)
    categories = parse_csv_lower(args.categories) if args.categories else None
    types = parse_csv_lower(args.types) if args.types else None

    if categories:
        unknown_categories = categories - OUTPUT_CATEGORIES
        if unknown_categories:
            parser.error(f"unknown --categories value(s): {', '.join(sorted(unknown_categories))}")

    if not yoo_root.exists():
        raise SystemExit(f"YooAssets root not found: {yoo_root}")

    package_rows = [package_report_row(package_root) for package_root in iter_package_roots(yoo_root, packages)]
    if args.list_packages:
        print(json.dumps(package_rows, ensure_ascii=False, indent=2))
        return 0

    bundle_paths = list(iter_bundle_files(yoo_root, packages))
    total_bundles = len(bundle_paths)
    selected_bundles = bundle_paths[: args.limit] if args.limit else bundle_paths

    manifest_index = None
    if not args.no_manifest_check:
        manifest_index = build_manifest_index(yoo_root, packages)

    unitypy = None
    if not args.no_export:
        unitypy = import_unitypy(args.deps_dir or None)

    options = ExportOptions(
        out_root=out_root,
        execute=args.execute,
        keep_bundles=args.keep_bundles,
        no_export=args.no_export,
        categories=categories,
        types=types,
        ui_packages=parse_csv_lower(args.ui_packages),
        model_packages=parse_csv_lower(args.model_packages),
        effects_packages=parse_csv_lower(args.effects_packages),
        animation_packages=parse_csv_lower(args.animation_packages),
        unitypy=unitypy,
    )
    ctx = ExportContext(options=options, used_outputs=set(), manifest_index=manifest_index)

    asset_rows: list[dict[str, Any]] = []
    bundle_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    processed = 0
    progress = ProgressReporter(len(selected_bundles), args.progress_style, args.progress_every)
    if selected_bundles and args.progress_style != "none":
        print(
            f"Processing {len(selected_bundles)} bundle(s) "
            f"from {total_bundles} discovered bundle(s). "
            f"manifest_refs={len(manifest_index.rows) if manifest_index else 'skipped'}",
            flush=True,
        )
    for package_root, data_path in selected_bundles:
        processed += 1

        try:
            bundle = classify_bundle(data_path, package_root)
            manifest_reference, manifest_match = manifest_match_for_bundle(bundle.hash_name, manifest_index)
            bundle_rows.append(
                {
                    "package": bundle.package,
                    "bundle_hash": bundle.hash_name,
                    "mode": bundle.mode,
                    "source": str(bundle.source_path),
                    "length": bundle.source_path.stat().st_size,
                    "raw_head": bundle.raw_head[:16].hex(" "),
                    "decoded_head": bundle.decoded_head[:16].hex(" ") if bundle.decoded_head else "",
                    "manifest_reference": manifest_reference,
                    "manifest_match": manifest_match,
                }
            )

            if bundle.mode.endswith("_unityfs") and bundle.unity_bytes:
                if args.keep_bundles:
                    target = out_root / "decrypted_bundles" / bundle.package / f"{bundle.hash_name}.bundle"
                    write_bytes(target, bundle.unity_bytes, args.execute)

                if not args.no_export:
                    env = load_unity_env(unitypy, bundle.unity_bytes)
                    for obj in env.objects:
                        asset_rows.extend(export_object(obj, bundle, ctx))
            elif bundle.unity_bytes:
                if category_is_enabled("raw", options):
                    target = out_root / "raw" / bundle.package / f"{bundle.hash_name}.bin"
                    write_bytes(target, bundle.unity_bytes, args.execute)

        except Exception as exc:
            errors.append(
                {
                    "source": str(data_path),
                    "error": str(exc),
                    "trace": traceback.format_exc(limit=6),
                }
            )

        progress.update(processed, len(asset_rows), len(errors), f"{package_root.name}/{data_path.parent.name}")
    progress.finish()

    bundle_modes = Counter(row["mode"] for row in bundle_rows)
    asset_statuses = Counter(row["status"] for row in asset_rows)
    package_counts = Counter(row["package"] for row in bundle_rows)
    duration_sec = round(time.time() - start_time, 3)
    summary = {
        "execute": args.execute,
        "duration_sec": duration_sec,
        "yoo_root": str(yoo_root),
        "out": str(out_root),
        "packages": sorted(packages) if packages else "all",
        "categories": sorted(categories) if categories else "all",
        "types": sorted(types) if types else "all",
        "processed_bundles": processed,
        "discovered_bundles": total_bundles,
        "asset_rows": len(asset_rows),
        "errors": len(errors),
        "manifest_check": "skipped" if manifest_index is None else "static_scan",
        "manifest_refs": 0 if manifest_index is None else len(manifest_index.rows),
        "bundle_modes": dict(bundle_modes),
        "asset_statuses": dict(asset_statuses),
        "package_counts": dict(package_counts),
        "note": "dry-run only; add --execute to write files" if not args.execute else "files written",
    }

    if args.execute:
        out_root.mkdir(parents=True, exist_ok=True)
        write_csv(out_root / "package_report.csv", PACKAGE_FIELDS, package_rows)
        write_csv(out_root / "bundles.csv", BUNDLE_FIELDS, bundle_rows)
        write_csv(out_root / "assets.csv", ASSET_FIELDS, asset_rows)
        if manifest_index is not None:
            write_csv(out_root / "manifest_refs.csv", MANIFEST_REF_FIELDS, manifest_index.rows)
        (out_root / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors and args.fail_on_error:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
