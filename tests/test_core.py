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
