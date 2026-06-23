from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import xzy_yooasset_extractor as extractor


class CoreExtractorTests(unittest.TestCase):
    def test_xor_with_tail_key_roundtrip(self) -> None:
        plain = b"UnityFS\x00payload-data"
        key = bytes(range(16))
        encrypted = bytes(plain[i] ^ key[i % 16] for i in range(len(plain))) + key

        self.assertEqual(extractor.xor_with_tail_key(encrypted), plain)

    def test_classify_plain_unityfs_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "Icon"
            data_path = package_root / "BundleFiles" / "00" / "hash_plain" / "__data"
            data_path.parent.mkdir(parents=True)
            data_path.write_bytes(b"UnityFS\x00raw")

            bundle = extractor.classify_bundle(data_path, package_root)

            self.assertEqual(bundle.package, "Icon")
            self.assertEqual(bundle.hash_name, "hash_plain")
            self.assertEqual(bundle.mode, "plain_unityfs")
            self.assertEqual(bundle.unity_bytes, b"UnityFS\x00raw")

    def test_classify_tail16_xor_unityfs_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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

    def test_iter_bundle_files_finds_data_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            yoo_root = Path(tmp) / "yoo"
            first = yoo_root / "Icon" / "BundleFiles" / "00" / "hash_a" / "__data"
            second = yoo_root / "Main" / "BundleFiles" / "01" / "hash_b" / "__data"
            ignored = yoo_root / "Background" / "ManifestFiles" / "Background.bytes"
            for path in (first, second, ignored):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")

            all_paths = [path for _, path in extractor.iter_bundle_files(yoo_root, None)]
            icon_paths = [path for _, path in extractor.iter_bundle_files(yoo_root, {"Icon"})]

            self.assertEqual(all_paths, [first, second])
            self.assertEqual(icon_paths, [first])

    def test_package_report_tracks_missing_bundle_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "Background"
            manifest = package_root / "ManifestFiles" / "Background.bytes"
            manifest.parent.mkdir(parents=True)
            manifest.write_bytes(b"manifest")

            row = extractor.package_report_row(package_root)

            self.assertEqual(row["package"], "Background")
            self.assertFalse(row["has_bundle_files"])
            self.assertEqual(row["bundle_count"], 0)
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
            ui_packages={"icon", "background", "main", "spine"},
            model_packages={"charactermesh", "art3d"},
            animation_packages={"spine"},
        )

        self.assertEqual(extractor.category_for_type("Texture2D", "sheet", "Spine", options), "ui")
        self.assertEqual(extractor.category_for_type("TextAsset", "skeleton", "Spine", options), "animation")
        self.assertEqual(extractor.category_for_type("Mesh", "body", "CharacterMesh", options), "models")


if __name__ == "__main__":
    unittest.main()
