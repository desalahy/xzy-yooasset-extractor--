from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import xzy_yooasset_extractor as extractor


TEST_TMP_BASE = Path(os.environ.get("XZY_EXTRACTOR_TEST_TMP", r"E:\XZYTool\_extractor_test_tmp"))


def manifest_string(value: str) -> bytes:
    data = value.encode("utf-8")
    return len(data).to_bytes(2, "little") + data


def build_rawfile_manifest(asset_rows: list[tuple[str, str, str, str, int]]) -> bytes:
    blob = bytearray(b"OOY\x00")
    blob.extend(manifest_string("2.3.1"))
    blob.extend(b"\x01\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00")
    blob.extend(manifest_string("RawFileBuildPipeline"))
    blob.extend(manifest_string("BattlePacket"))
    blob.extend(manifest_string("3.1.0.485"))
    blob.extend(manifest_string("2026/6/24 18:34:28"))
    blob.extend(len(asset_rows).to_bytes(4, "little", signed=True))
    for index, (asset_name, asset_path, _bundle_name, _bundle_hash, _bundle_size) in enumerate(asset_rows):
        blob.extend(manifest_string(asset_name))
        blob.extend(manifest_string(asset_path))
        blob.extend(b"\x00\x00\x00\x00")
        blob.extend(index.to_bytes(4, "little", signed=True))
        blob.extend(b"\x00\x00")
    blob.extend(len(asset_rows).to_bytes(4, "little", signed=True))
    for _asset_name, _asset_path, bundle_name, bundle_hash, bundle_size in asset_rows:
        blob.extend(manifest_string(bundle_name))
        blob.extend(b"\x00\x00\x00\x00")
        blob.extend(manifest_string(bundle_hash))
        blob.extend(manifest_string("checksum"))
        blob.extend(bundle_size.to_bytes(8, "little"))
        blob.extend(b"\x00\x00\x00\x00\x00")
    return bytes(blob)


def build_builtin_rawfile_manifest(asset_rows: list[tuple[str, str, str, str, int]]) -> bytes:
    blob = bytearray(b"OOY\x00")
    blob.extend(manifest_string("2.3.1"))
    blob.extend(b"\x01\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00")
    blob.extend(manifest_string("RawFileBuildPipeline"))
    blob.extend(manifest_string("Packet"))
    blob.extend(manifest_string("3.1.0.465"))
    blob.extend(manifest_string("2026/6/5 16:01:31"))
    blob.extend(len(asset_rows).to_bytes(4, "little", signed=True))
    for index, (asset_name, asset_path, _bundle_name, _bundle_hash, _bundle_size) in enumerate(asset_rows):
        blob.extend(manifest_string(asset_name))
        blob.extend(manifest_string(asset_path))
        blob.extend(b"\x00\x00\x01\x00")
        blob.extend(manifest_string("Builtin"))
        blob.extend(index.to_bytes(4, "little", signed=True))
        blob.extend(b"\x00\x00")
    blob.extend(len(asset_rows).to_bytes(4, "little", signed=True))
    for _asset_name, _asset_path, bundle_name, bundle_hash, bundle_size in asset_rows:
        blob.extend(manifest_string(bundle_name))
        blob.extend(b"\x00\x00\x00\x00")
        blob.extend(manifest_string(bundle_hash))
        blob.extend(manifest_string("checksum"))
        blob.extend(bundle_size.to_bytes(8, "little"))
        blob.extend(b"\x00\x01\x00")
        blob.extend(manifest_string("Builtin"))
        blob.extend(b"\x00\x00")
    return bytes(blob)


@contextmanager
def temp_workspace():
    TEST_TMP_BASE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TEST_TMP_BASE) as tmp:
        yield Path(tmp)


class CoreExtractorTests(unittest.TestCase):
    def test_xor_with_tail_key_roundtrip(self) -> None:
        plain = b"UnityFS\x00payload-data"
        key = bytes(range(16))
        encrypted = bytes(plain[i] ^ key[i % 16] for i in range(len(plain))) + key

        self.assertEqual(extractor.xor_with_tail_key(encrypted), plain)

    def test_classify_plain_unityfs_bundle(self) -> None:
        with temp_workspace() as tmp:
            package_root = Path(tmp) / "Icon"
            data_path = package_root / "BundleFiles" / "00" / "hash_plain" / "__data"
            data_path.parent.mkdir(parents=True)
            data_path.write_bytes(b"UnityFS\x00raw")

            bundle = extractor.classify_bundle(data_path, package_root)

            self.assertEqual(bundle.package, "Icon")
            self.assertEqual(bundle.hash_name, "hash_plain")
            self.assertEqual(bundle.mode, "plain_unityfs")
            self.assertEqual(bundle.unity_bytes, b"UnityFS\x00raw")

    def test_classify_streaming_plain_unityfs_bundle(self) -> None:
        with temp_workspace() as tmp:
            package_root = Path(tmp) / "Icon"
            data_path = package_root / "abcdef0123456789.bundle"
            data_path.parent.mkdir(parents=True)
            data_path.write_bytes(b"UnityFS\x00streaming")

            bundle = extractor.classify_bundle(data_path, package_root, "streaming_assets", data_path.stem)

            self.assertEqual(bundle.layout, "streaming_assets")
            self.assertEqual(bundle.package, "Icon")
            self.assertEqual(bundle.hash_name, "abcdef0123456789")
            self.assertEqual(bundle.mode, "plain_unityfs")

    def test_classify_tail16_xor_unityfs_bundle(self) -> None:
        with temp_workspace() as tmp:
            package_root = Path(tmp) / "Icon"
            data_path = package_root / "BundleFiles" / "00" / "hash_xor" / "__data"
            data_path.parent.mkdir(parents=True)

            plain = b"UnityFS\x00decoded"
            key = b"0123456789abcdef"
            encrypted = bytes(plain[i] ^ key[i % 16] for i in range(len(plain))) + key
            data_path.write_bytes(encrypted)

            bundle = extractor.classify_bundle(data_path, package_root)

            self.assertEqual(bundle.mode, "tail16_xor_unityfs")
            self.assertEqual(bundle.unity_bytes, plain)
            self.assertTrue(bundle.decoded_head.startswith(b"UnityFS"))

    def test_classify_lightweight_mode_keeps_decoded_head_only(self) -> None:
        with temp_workspace() as tmp:
            package_root = Path(tmp) / "Icon"
            data_path = package_root / "BundleFiles" / "00" / "hash_xor" / "__data"
            data_path.parent.mkdir(parents=True)

            plain = b"UnityFS\x00decoded"
            key = b"0123456789abcdef"
            encrypted = bytes(plain[i] ^ key[i % 16] for i in range(len(plain))) + key
            data_path.write_bytes(encrypted)

            bundle = extractor.classify_bundle(data_path, package_root, load_bytes=False)

            self.assertEqual(bundle.mode, "tail16_xor_unityfs")
            self.assertIsNone(bundle.unity_bytes)
            self.assertTrue(bundle.decoded_head.startswith(b"UnityFS"))

    def test_classify_non_unity_keeps_original_raw_bytes(self) -> None:
        with temp_workspace() as tmp:
            package_root = Path(tmp) / "BattlePacket"
            data_path = package_root / "BundleFiles" / "00" / "hash_packet" / "__data"
            data_path.parent.mkdir(parents=True)

            packet_like = b"\x01\x21\x03\x00\x00packet-index" + b"x" * 16
            data_path.write_bytes(packet_like)

            bundle = extractor.classify_bundle(data_path, package_root)

            self.assertEqual(bundle.mode, "non_unity_raw")
            self.assertEqual(bundle.unity_bytes, packet_like)
            self.assertFalse(bundle.decoded_head.startswith(b"UnityFS"))

    def test_resolve_yoo_roots_finds_hot_and_streaming_sources(self) -> None:
        with temp_workspace() as tmp:
            game_root = Path(tmp) / "game"
            hot = game_root / "XzyLauncher_Data" / "yoo"
            streaming = game_root / "XzyLauncher_Data" / "StreamingAssets" / "yoo"
            (hot / "Icon").mkdir(parents=True)
            (streaming / "Icon").mkdir(parents=True)

            roots = extractor.resolve_yoo_roots(str(game_root), "", "all")

            self.assertEqual([root.layout for root in roots], ["hot_update", "streaming_assets"])
            self.assertEqual([root.path for root in roots], [hot.resolve(), streaming.resolve()])

    def test_iter_bundle_files_finds_hot_and_streaming_files(self) -> None:
        with temp_workspace() as tmp:
            hot_root = Path(tmp) / "hot_yoo"
            streaming_root = Path(tmp) / "streaming_yoo"
            first = hot_root / "Icon" / "BundleFiles" / "00" / "hash_a" / "__data"
            second = hot_root / "Main" / "BundleFiles" / "01" / "hash_b" / "__data"
            streaming = streaming_root / "Icon" / "stream_hash.bundle"
            ignored = hot_root / "Background" / "ManifestFiles" / "Background.bytes"
            ignored_rawfile = streaming_root / "Icon" / "raw_asset.rawfile"
            for path in (first, second, ignored):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            streaming.parent.mkdir(parents=True, exist_ok=True)
            streaming.write_bytes(b"UnityFS\x00stream")
            ignored_rawfile.write_bytes(b"raw")

            roots = [
                extractor.YooRoot(hot_root, "hot_update"),
                extractor.YooRoot(streaming_root, "streaming_assets"),
            ]
            all_candidates = list(extractor.iter_bundle_files(roots, None))
            all_paths = [candidate.data_path for candidate in all_candidates]
            all_hashes = [candidate.hash_name for candidate in all_candidates]
            icon_paths = [candidate.data_path for candidate in extractor.iter_bundle_files(roots, {"Icon"})]

            self.assertEqual(all_paths, [first, second, streaming])
            self.assertEqual(all_hashes, ["hash_a", "hash_b", "stream_hash"])
            self.assertEqual(icon_paths, [first, streaming])

    def test_iter_raw_files_finds_streaming_rawfile_payloads(self) -> None:
        with temp_workspace() as tmp:
            streaming_root = Path(tmp) / "streaming_yoo"
            raw_file = streaming_root / "AnimationPacket" / "packet_001.rawfile"
            raw_file.parent.mkdir(parents=True)
            raw_file.write_bytes(b"raw")

            roots = [extractor.YooRoot(streaming_root, "streaming_assets")]
            raw_files = list(extractor.iter_raw_files(roots, {"AnimationPacket"}))

            self.assertEqual(len(raw_files), 1)
            self.assertEqual(raw_files[0].data_path, raw_file)
            self.assertEqual(raw_files[0].hash_name, "packet_001")

    def test_rawfile_output_path_and_row_use_raw_category(self) -> None:
        with temp_workspace() as tmp:
            out_root = Path(tmp) / "out"
            package_root = Path(tmp) / "yoo" / "AnimationPacket"
            raw_path = package_root / "sub" / "packet_001.rawfile"
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(b"raw")

            options = extractor.ExportOptions(
                out_root=out_root,
                execute=True,
                keep_bundles=False,
                no_export=True,
                categories=None,
                types=None,
                ui_packages={"icon"},
                model_packages={"charactermesh"},
                effects_packages={"battlepacket"},
                animation_packages={"animationpacket"},
            )
            ctx = extractor.ExportContext(options=options, used_outputs=set(), manifest_index=None)
            raw_file = extractor.RawFileCandidate(
                extractor.YooRoot(package_root.parent, "streaming_assets"),
                package_root,
                raw_path,
                raw_path.stem,
            )

            target = extractor.rawfile_output_path(ctx, raw_file)
            row = extractor.rawfile_row(raw_file, target, "copied_rawfile", out_root)

            self.assertEqual(target, out_root / "assets" / "raw" / "streaming_assets" / "AnimationPacket" / "sub" / "packet_001.rawfile")
            self.assertEqual(row["layout"], "streaming_assets")
            self.assertEqual(row["category"], "raw")
            self.assertEqual(row["bundle_mode"], "rawfile")

    def test_raw_bundle_row_uses_raw_category(self) -> None:
        with temp_workspace() as tmp:
            out_root = Path(tmp) / "out"
            source = Path(tmp) / "yoo" / "BattlePacket" / "BundleFiles" / "00" / "hash_packet" / "__data"
            target = out_root / "raw" / "hot_update" / "BattlePacket" / "hash_packet.bin"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"\x01\x21\x03\x00\x00packet")
            bundle = extractor.BundleInput(
                "hot_update",
                "BattlePacket",
                "hash_packet",
                source,
                "non_unity_raw",
                source.read_bytes(),
                b"\x01\x21\x03\x00\x00",
                b"",
            )

            row = extractor.raw_bundle_row(bundle, target, "exported_raw_bundle", out_root, None)

            self.assertEqual(row["type"], "RawBundle")
            self.assertEqual(row["category"], "raw")
            self.assertEqual(row["bundle_mode"], "non_unity_raw")
            self.assertEqual(row["output"], "raw\\hot_update\\BattlePacket\\hash_packet.bin")

    def test_gameobject_prefab_export_routes_to_prefabs_json(self) -> None:
        with temp_workspace() as tmp:
            out_root = Path(tmp) / "out"
            bundle = extractor.BundleInput(
                "hot_update",
                "BattleScene",
                "hash_scene",
                Path(tmp) / "yoo" / "BattleScene" / "BundleFiles" / "00" / "hash_scene" / "__data",
                "plain_unityfs",
                None,
                b"UnityFS\x00",
                b"UnityFS\x00",
            )
            options = extractor.ExportOptions(
                out_root=out_root,
                execute=True,
                keep_bundles=False,
                no_export=False,
                categories=None,
                types=None,
                ui_packages={"icon", "background", "main", "spine"},
                model_packages={"charactermesh", "art3d"},
                effects_packages={"battlepacket"},
                animation_packages={"spine"},
            )
            ctx = extractor.ExportContext(options=options, used_outputs=set(), manifest_index=None)

            class DummyGameObject:
                type = type("T", (), {"name": "GameObject"})()
                path_id = 42

                def read(self):
                    return self

                def parse_as_object(self):
                    return self

                def parse_as_dict(self):
                    return {"m_Name": "HeroRoot", "m_IsActive": True, "m_Component": []}

            rows = extractor.export_object(DummyGameObject(), bundle, ctx)

            self.assertEqual(rows[0]["category"], "prefabs")
            self.assertEqual(rows[0]["status"], "exported_prefab_json")
            self.assertTrue((out_root / "assets" / "prefabs" / "hot_update" / "BattleScene" / "hash_scene" / "HeroRoot__GameObject_42.json").exists())

    def test_prefab_graph_is_written_per_bundle(self) -> None:
        with temp_workspace() as tmp:
            out_root = Path(tmp) / "out"
            bundle = extractor.BundleInput(
                "hot_update",
                "BattleScene",
                "hash_scene",
                Path(tmp) / "yoo" / "BattleScene" / "BundleFiles" / "00" / "hash_scene" / "__data",
                "plain_unityfs",
                None,
                b"UnityFS\x00",
                b"UnityFS\x00",
            )
            options = extractor.ExportOptions(
                out_root=out_root,
                execute=True,
                keep_bundles=False,
                no_export=False,
                categories=None,
                types=None,
                ui_packages={"icon", "background", "main", "spine"},
                model_packages={"charactermesh", "art3d"},
                effects_packages={"battlepacket"},
                animation_packages={"spine"},
            )
            ctx = extractor.ExportContext(options=options, used_outputs=set(), manifest_index=None)

            class DummyTransform:
                type = type("T", (), {"name": "Transform"})()
                path_id = 7

                def read(self):
                    return self

                def parse_as_object(self):
                    return self

                def parse_as_dict(self):
                    return {"m_Name": "HeroRoot", "m_Children": []}

            extractor.export_object(DummyTransform(), bundle, ctx)
            rows = extractor.write_prefab_graph(ctx, bundle)

            graph_file = out_root / "assets" / "prefabs" / "hot_update" / "BattleScene" / "hash_scene" / "prefab_graph.json"
            self.assertTrue(graph_file.exists())
            self.assertEqual(rows[0]["type"], "PrefabGraph")
            payload = json.loads(graph_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["bundle_hash"], "hash_scene")
            self.assertEqual(payload["node_count"], 1)
            self.assertEqual(payload["nodes"][0]["type"], "Transform")
            self.assertEqual(payload["nodes"][0]["name"], "HeroRoot")

    def test_package_report_tracks_missing_bundle_files(self) -> None:
        with temp_workspace() as tmp:
            yoo_root = extractor.YooRoot(Path(tmp), "hot_update")
            package_root = Path(tmp) / "Background"
            manifest = package_root / "ManifestFiles" / "Background.bytes"
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(b"manifest")

            row = extractor.package_report_row(yoo_root, package_root)

            self.assertEqual(row["package"], "Background")
            self.assertFalse(row["has_bundle_files"])
            self.assertEqual(row["bundle_count"], 0)
            self.assertEqual(row["bundle_file_count"], 0)
            self.assertEqual(row["streaming_bundle_count"], 0)
            self.assertEqual(row["manifest_file_count"], 1)

    def test_safe_name_removes_windows_forbidden_chars(self) -> None:
        name = extractor.safe_name(r"Assets/GameData/UiIcons/a:b*c?.png")

        self.assertEqual(name, "a_b_c_.png")

    def test_category_rules_prioritize_ui_images(self) -> None:
        options = extractor.ExportOptions(
            out_root=Path("out"),
            execute=False,
            keep_bundles=False,
            no_export=False,
            categories=None,
            types=None,
            ui_packages={"icon", "background", "main", "spine"},
            model_packages={"charactermesh", "art3d"},
            effects_packages={"effect"},
            animation_packages={"spine"},
        )

        self.assertEqual(extractor.category_for_type("Texture2D", "sheet", "Spine", options), "ui")
        self.assertEqual(extractor.category_for_type("TextAsset", "skeleton", "Spine", options), "animation")
        self.assertEqual(extractor.category_for_type("Mesh", "body", "CharacterMesh", options), "models")

    def test_category_rules_include_audio_and_effects(self) -> None:
        options = extractor.ExportOptions(
            out_root=Path("out"),
            execute=False,
            keep_bundles=False,
            no_export=False,
            categories=None,
            types=None,
            ui_packages={"icon", "background", "main", "spine"},
            model_packages={"charactermesh", "art3d"},
            effects_packages={"battlepacket"},
            animation_packages={"spine"},
        )

        self.assertEqual(extractor.category_for_type("AudioClip", "opening_theme", "Bgm", options), "bgm")
        self.assertEqual(extractor.category_for_type("AudioClip", "click", "Se", options), "audio")
        self.assertEqual(extractor.category_for_type("ParticleSystem", "hit_spark", "BattlePacket", options), "effects")

    def test_category_rules_route_prefab_tree_to_prefabs(self) -> None:
        options = extractor.ExportOptions(
            out_root=Path("out"),
            execute=False,
            keep_bundles=False,
            no_export=False,
            categories=None,
            types=None,
            ui_packages={"icon", "background", "main", "spine"},
            model_packages={"charactermesh", "art3d"},
            effects_packages={"battlepacket"},
            animation_packages={"spine"},
        )

        self.assertEqual(extractor.category_for_type("GameObject", "HeroRoot", "BattleScene", options), "prefabs")
        self.assertEqual(extractor.category_for_type("Transform", "HeroRoot", "BattleScene", options), "prefabs")
        self.assertEqual(extractor.category_for_type("MonoBehaviour", "HeroRoot", "BattleScene", options), "prefabs")
        self.assertEqual(extractor.category_for_type("CanvasRenderer", "HeroRoot", "BattleScene", options), "prefabs")

    def test_export_filter_status_checks_category_and_type(self) -> None:
        options = extractor.ExportOptions(
            out_root=Path("out"),
            execute=False,
            keep_bundles=False,
            no_export=False,
            categories={"bgm"},
            types={"audioclip"},
            ui_packages={"icon", "background", "main", "spine"},
            model_packages={"charactermesh", "art3d"},
            effects_packages={"effect"},
            animation_packages={"spine"},
        )

        self.assertEqual(extractor.export_filter_status("ui", "Texture2D", options), "skipped_category")
        self.assertEqual(extractor.export_filter_status("bgm", "Texture2D", options), "skipped_type")
        self.assertEqual(extractor.export_filter_status("bgm", "AudioClip", options), "")

    def test_category_is_enabled_handles_raw_outputs(self) -> None:
        options = extractor.ExportOptions(
            out_root=Path("out"),
            execute=False,
            keep_bundles=False,
            no_export=False,
            categories={"ui"},
            types=None,
            ui_packages={"icon", "background", "main", "spine"},
            model_packages={"charactermesh", "art3d"},
            effects_packages={"effect"},
            animation_packages={"spine"},
        )

        self.assertTrue(extractor.category_is_enabled("ui", options))
        self.assertFalse(extractor.category_is_enabled("raw", options))

    def test_manifest_index_marks_bundle_and_asset_references(self) -> None:
        with temp_workspace() as tmp:
            yoo_root = Path(tmp) / "yoo"
            manifest = yoo_root / "Icon" / "ManifestFiles" / "Icon.bytes"
            manifest.parent.mkdir(parents=True)
            bundle_hash = "0123456789abcdef"
            manifest.write_bytes(
                f"{bundle_hash}\nAssets/GameData/UiIcons/start_button.png\n".encode("utf-8")
            )

            index = extractor.build_manifest_index([extractor.YooRoot(yoo_root, "hot_update")], None)

            self.assertEqual(extractor.manifest_match_for_bundle(bundle_hash, index), ("referenced", bundle_hash))
            self.assertEqual(
                extractor.manifest_match_for_asset("start_button", bundle_hash, index),
                ("referenced", "assets/gamedata/uiicons/start_button.png"),
            )
            self.assertGreaterEqual(len(index.rows), 2)

    def test_manifest_index_reads_streaming_manifest_files(self) -> None:
        with temp_workspace() as tmp:
            yoo_root = Path(tmp) / "yoo"
            manifest = yoo_root / "Icon" / "Icon.bytes"
            manifest.parent.mkdir(parents=True)
            bundle_hash = "abcdef0123456789"
            manifest.write_bytes(
                f"{bundle_hash}\nAssets/GameData/UiIcons/stream_button.png\n".encode("utf-8")
            )

            index = extractor.build_manifest_index([extractor.YooRoot(yoo_root, "streaming_assets")], None)

            self.assertEqual(extractor.manifest_match_for_bundle(bundle_hash, index), ("referenced", bundle_hash))
            self.assertEqual(index.rows[0]["layout"], "streaming_assets")

    def test_rawfile_manifest_maps_bundle_hash_to_asset_name(self) -> None:
        with temp_workspace() as tmp:
            yoo_root = Path(tmp) / "yoo"
            manifest = yoo_root / "BattlePacket" / "ManifestFiles" / "BattlePacket.bytes"
            manifest.parent.mkdir(parents=True)
            bundle_hash = "115a22cd2380a915ade0fc239edaf3e0"
            manifest.write_bytes(
                build_rawfile_manifest(
                    [
                        (
                            "GameBehavior18",
                            "Assets/GameData/BattlePackets/GameBehavior18.p",
                            "battlepacket_assets_gamedata_battlepackets_gamebehavior18_p.rawfile",
                            bundle_hash,
                            10470365,
                        )
                    ]
                )
            )

            parsed = extractor.parse_rawfile_manifest(manifest.read_bytes())
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["bundles"][0]["asset_name"], "GameBehavior18")
            self.assertEqual(parsed["bundles"][0]["bundle_hash"], bundle_hash)

            index = extractor.build_manifest_index([extractor.YooRoot(yoo_root, "hot_update")], None)

            self.assertEqual(index.hash_to_assets[bundle_hash][0]["asset_name"], "GameBehavior18")
            self.assertEqual(index.hash_to_assets[bundle_hash][0]["asset_path"], "Assets/GameData/BattlePackets/GameBehavior18.p")

    def test_builtin_rawfile_manifest_maps_packet_hash_to_asset_name(self) -> None:
        with temp_workspace() as tmp:
            yoo_root = Path(tmp) / "yoo"
            manifest = yoo_root / "Packet" / "Packet_3.1.0.465.bytes"
            manifest.parent.mkdir(parents=True)
            bundle_hash = "957e8c52b0ee4a777f9a0de6f6580246"
            manifest.write_bytes(
                build_builtin_rawfile_manifest(
                    [
                        (
                            "UiTables",
                            "Assets/GameData/Packets/UiTables.p",
                            "packet_assets_gamedata_packets_uitables_p.rawfile",
                            bundle_hash,
                            2787773,
                        )
                    ]
                )
            )

            parsed = extractor.parse_rawfile_manifest(manifest.read_bytes())
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["asset_record_mode"], "builtin")
            self.assertEqual(parsed["bundles"][0]["asset_name"], "UiTables")
            self.assertEqual(parsed["bundles"][0]["asset_path"], "Assets/GameData/Packets/UiTables.p")

            index = extractor.build_manifest_index([extractor.YooRoot(yoo_root, "streaming_assets")], None)

            self.assertEqual(index.hash_to_assets[bundle_hash][0]["asset_name"], "UiTables")
            self.assertEqual(index.hash_to_assets[bundle_hash][0]["asset_path"], "Assets/GameData/Packets/UiTables.p")

    def test_cli_workers_no_export_writes_stable_indexes(self) -> None:
        with temp_workspace() as tmp:
            project_root = Path(__file__).resolve().parents[1]
            script = project_root / "xzy_yooasset_extractor.py"
            yoo_root = Path(tmp) / "yoo"
            package_root = yoo_root / "Icon"
            plain_path = package_root / "BundleFiles" / "00" / "hash_plain" / "__data"
            xor_path = package_root / "BundleFiles" / "01" / "hash_xor" / "__data"
            plain_path.parent.mkdir(parents=True)
            xor_path.parent.mkdir(parents=True)
            plain_path.write_bytes(b"UnityFS\x00plain")

            payload = b"UnityFS\x00decoded"
            key = b"0123456789abcdef"
            xor_path.write_bytes(bytes(payload[i] ^ key[i % 16] for i in range(len(payload))) + key)

            out_root = Path(tmp) / "out"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--yoo-root",
                    str(yoo_root),
                    "--out",
                    str(out_root),
                    "--limit",
                    "0",
                    "--no-export",
                    "--execute",
                    "--workers",
                    "2",
                    "--progress-style",
                    "none",
                    "--no-manifest-check",
                ],
                cwd=project_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads((out_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["workers"], 2)
            self.assertEqual(summary["processed_bundles"], 2)
            self.assertEqual(summary["errors"], 0)

            with (out_root / "bundles.csv").open(newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual([row["bundle_hash"] for row in rows], ["hash_plain", "hash_xor"])
            self.assertEqual([row["mode"] for row in rows], ["plain_unityfs", "tail16_xor_unityfs"])


if __name__ == "__main__":
    unittest.main()
