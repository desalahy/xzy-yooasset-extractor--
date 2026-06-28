from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path
from typing import Any

from .manifest import manifest_match_for_asset
from .models import BundleInput, ExportContext, ExportOptions, ManifestIndex, RawFileCandidate
from .utils import safe_name


def import_unitypy() -> Any:
    try:
        module = importlib.import_module("UnityPy")
    except ImportError as exc:
        raise RuntimeError("UnityPy is not installed. Run: uv sync, then use uv run python ...") from exc

    has_loader = callable(getattr(module, "load", None)) or callable(getattr(module, "Environment", None))
    if not has_loader:
        raise RuntimeError(
            "Imported a UnityPy module without load/Environment. "
            f"module_file={getattr(module, '__file__', None)!r}. "
            "Check the active uv environment with: uv run python -c \"import UnityPy; print(UnityPy.__file__)\"."
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


def _obj_type_name(obj: Any) -> str:
    return getattr(getattr(obj, "type", None), "name", str(getattr(obj, "type", "Unknown")))


def _obj_path_id(obj: Any) -> Any:
    return getattr(obj, "path_id", getattr(obj, "m_PathID", ""))


def _display_name(data: Any, type_name: str, path_id: Any) -> str:
    if isinstance(data, dict):
        for key in ("m_Name", "name", "m_AssetName", "m_OriginalName", "m_ScriptName"):
            value = data.get(key, "")
            if isinstance(value, str) and value.strip():
                return value.strip()
    for attr in ("m_Name", "name", "m_AssetName", "m_OriginalName", "m_ScriptName"):
        value = getattr(data, attr, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{type_name}_{path_id}" if path_id != "" else type_name


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


def _safe_parse_object(obj: Any) -> Any:
    parser = getattr(obj, "parse_as_object", None)
    if callable(parser):
        return parser()
    reader = getattr(obj, "object_reader", None)
    if reader is not None and callable(getattr(reader, "parse_as_object", None)):
        return reader.parse_as_object()
    return obj


def _safe_parse_dict(obj: Any) -> dict[str, Any] | None:
    parser = getattr(obj, "parse_as_dict", None)
    if callable(parser):
        try:
            value = parser()
            if isinstance(value, dict):
                return value
        except Exception:
            return None
    reader = getattr(obj, "object_reader", None)
    if reader is not None and callable(getattr(reader, "parse_as_dict", None)):
        try:
            value = reader.parse_as_dict()
            if isinstance(value, dict):
                return value
        except Exception:
            return None
    return None


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "__dict__") and not isinstance(value, type):
        data: dict[str, Any] = {}
        for key, item in vars(value).items():
            if key.startswith("_"):
                continue
            data[key] = _jsonable(item)
        if data:
            return data
    if hasattr(value, "path_id"):
        return {"path_id": _obj_path_id(value)}
    return str(value)


def _component_ref(value: Any) -> dict[str, Any]:
    if hasattr(value, "path_id") or hasattr(value, "m_PathID"):
        return {
            "path_id": str(_obj_path_id(value)),
            "type": _obj_type_name(value),
        }
    return {"value": _jsonable(value)}


def _append_prefab_node(ctx: ExportContext, bundle: BundleInput, type_name: str, asset_name: str, path_id: Any, payload: dict[str, Any]) -> None:
    key = (bundle.layout, bundle.package, bundle.hash_name)
    graph = ctx.prefab_graphs.setdefault(
        key,
        {
            "layout": bundle.layout,
            "package": bundle.package,
            "bundle_hash": bundle.hash_name,
            "bundle_mode": bundle.mode,
            "source": str(bundle.source_path),
            "nodes": [],
        },
    )
    node = {
        "type": type_name,
        "name": asset_name,
        "path_id": str(path_id),
    }
    node.update(payload)
    graph["nodes"].append(node)


def prefab_graph_output_path(ctx: ExportContext, bundle: BundleInput) -> Path:
    target = ctx.options.out_root / "assets" / "prefabs" / bundle.layout / bundle.package / bundle.hash_name / "prefab_graph.json"
    return reserve_output_path(ctx, target)


def prefab_graph_row(
    bundle: BundleInput,
    target: Path | None,
    status: str,
    out_root: Path,
    manifest_index: ManifestIndex | None = None,
) -> dict[str, Any]:
    output = ""
    if target:
        try:
            output = str(target.relative_to(out_root))
        except ValueError:
            output = str(target)
    manifest_reference, manifest_match = manifest_match_for_asset(bundle.hash_name, bundle.hash_name, manifest_index)
    return {
        "layout": bundle.layout,
        "package": bundle.package,
        "bundle_hash": bundle.hash_name,
        "bundle_mode": bundle.mode,
        "source": str(bundle.source_path),
        "type": "PrefabGraph",
        "path_id": "",
        "asset_name": "prefab_graph.json",
        "category": "prefabs",
        "output": output,
        "status": status,
        "manifest_reference": manifest_reference,
        "manifest_match": manifest_match,
    }


def write_prefab_graph(ctx: ExportContext, bundle: BundleInput) -> list[dict[str, Any]]:
    key = (bundle.layout, bundle.package, bundle.hash_name)
    graph = ctx.prefab_graphs.get(key)
    if not graph:
        return []

    target = prefab_graph_output_path(ctx, bundle)
    payload = {
        "layout": graph["layout"],
        "package": graph["package"],
        "bundle_hash": graph["bundle_hash"],
        "bundle_mode": graph["bundle_mode"],
        "source": graph["source"],
        "node_count": len(graph["nodes"]),
        "nodes": graph["nodes"],
        "roots": [node for node in graph["nodes"] if node["type"] == "GameObject"],
    }
    try:
        export_json = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        write_bytes(target, export_json, ctx.options.execute)
        row = prefab_graph_row(bundle, target, "exported_prefab_graph" if ctx.options.execute else "listed_prefab_graph", ctx.options.out_root, ctx.manifest_index)
    except Exception as exc:
        row = prefab_graph_row(bundle, None, f"prefab_graph_failed:{exc}", ctx.options.out_root, ctx.manifest_index)
    return [row]


def _prefab_export_rows(
    obj: Any,
    bundle: BundleInput,
    category: str,
    type_name: str,
    asset_name: str,
    out_root: Path,
    ctx: ExportContext,
) -> list[dict[str, Any]]:
    instance = _safe_parse_object(obj)
    dict_payload = _safe_parse_dict(obj)
    display_name = asset_name
    if dict_payload:
        display_name = _display_name(dict_payload, type_name, _obj_path_id(obj))
    target = object_output_path(ctx, bundle, category, type_name, display_name, _obj_path_id(obj), ".json")
    payload: dict[str, Any] = {
        "type": type_name,
        "name": display_name,
        "path_id": str(_obj_path_id(obj)),
    }
    if dict_payload:
        for key in (
            "m_Name",
            "m_Layer",
            "m_Tag",
            "m_IsActive",
            "m_Component",
            "m_Components",
            "m_Children",
            "m_Father",
            "m_Animator",
            "m_Animation",
            "m_Transform",
            "m_MeshFilter",
            "m_MeshRenderer",
            "m_SkinnedMeshRenderer",
            "m_Script",
            "m_GameObject",
        ):
            value = dict_payload.get(key)
            if value is not None:
                if key in {"m_Component", "m_Components", "m_Children"} and isinstance(value, list):
                    payload[key] = [_component_ref(item) for item in value]
                elif key in {"m_Animator", "m_Animation", "m_Transform", "m_MeshFilter", "m_MeshRenderer", "m_SkinnedMeshRenderer", "m_Script", "m_GameObject", "m_Father"}:
                    payload[key] = _component_ref(value) if value else None
                else:
                    payload[key] = _jsonable(value)

    for attr in (
        "m_Name",
        "m_Component",
        "m_Children",
        "m_Father",
        "m_Transform",
        "m_Animator",
        "m_Animation",
        "m_MeshFilter",
        "m_MeshRenderer",
        "m_SkinnedMeshRenderer",
        "m_Enabled",
    ):
        value = getattr(instance, attr, None)
        if value is not None:
            payload[attr] = _jsonable(value)

    if hasattr(instance, "m_Children") and "m_Children" not in payload:
        payload["m_Children"] = _jsonable(getattr(instance, "m_Children"))

    _append_prefab_node(ctx, bundle, type_name, display_name, _obj_path_id(obj), payload)

    try:
        export_json = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        write_bytes(target, export_json, ctx.options.execute)
        row = row_for(bundle, obj, type_name, asset_name, category, target, "exported_prefab_json", out_root, ctx.manifest_index)
    except Exception as exc:
        row = row_for(bundle, obj, type_name, asset_name, category, None, f"prefab_failed:{exc}", out_root, ctx.manifest_index)
    return [row]


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
    target = ctx.options.out_root / "assets" / category / bundle.layout / bundle.package / bundle.hash_name / filename
    return reserve_output_path(ctx, target)


def write_bytes(path: Path, data: bytes, execute: bool) -> None:
    if not execute:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def copy_file(source: Path, target: Path, execute: bool) -> None:
    if not execute:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


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
        "layout": bundle.layout,
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


def rawfile_output_path(ctx: ExportContext, raw_file: RawFileCandidate) -> Path:
    try:
        relative = raw_file.data_path.relative_to(raw_file.package_root)
    except ValueError:
        relative = Path(raw_file.data_path.name)
    safe_parts = [safe_name(part, "raw") for part in relative.parts]
    target = ctx.options.out_root / "assets" / "raw" / raw_file.root.layout / raw_file.package_root.name / Path(*safe_parts)
    return reserve_output_path(ctx, target)


def rawfile_row(raw_file: RawFileCandidate, target: Path | None, status: str, out_root: Path) -> dict[str, Any]:
    output = ""
    if target:
        try:
            output = str(target.relative_to(out_root))
        except ValueError:
            output = str(target)
    return {
        "layout": raw_file.root.layout,
        "package": raw_file.package_root.name,
        "bundle_hash": raw_file.hash_name,
        "bundle_mode": "rawfile",
        "source": str(raw_file.data_path),
        "type": "RawFile",
        "path_id": "",
        "asset_name": raw_file.data_path.name,
        "category": "raw",
        "output": output,
        "status": status,
        "manifest_reference": "not_checked",
        "manifest_match": "",
    }


def raw_bundle_row(
    bundle: BundleInput,
    target: Path | None,
    status: str,
    out_root: Path,
    manifest_index: ManifestIndex | None,
) -> dict[str, Any]:
    output = ""
    if target:
        try:
            output = str(target.relative_to(out_root))
        except ValueError:
            output = str(target)
    manifest_reference, manifest_match = manifest_match_for_asset(bundle.hash_name, bundle.hash_name, manifest_index)
    return {
        "layout": bundle.layout,
        "package": bundle.package,
        "bundle_hash": bundle.hash_name,
        "bundle_mode": bundle.mode,
        "source": str(bundle.source_path),
        "type": "RawBundle",
        "path_id": "",
        "asset_name": f"{bundle.hash_name}.bin",
        "category": "raw",
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
        type_name = _obj_type_name(obj)
        path_id = _obj_path_id(obj)
        asset_name = _display_name(data, type_name, path_id)
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

        if type_name == "GameObject":
            return _prefab_export_rows(obj, bundle, category, type_name, asset_name, out_root, ctx)

        if type_name in {"Transform", "RectTransform", "MonoBehaviour", "CanvasRenderer"}:
            return _prefab_export_rows(obj, bundle, category, type_name, asset_name, out_root, ctx)

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
