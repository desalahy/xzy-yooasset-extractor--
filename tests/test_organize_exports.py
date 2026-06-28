from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "organize_exports.py"
SPEC = importlib.util.spec_from_file_location("organize_exports", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
organize_exports = importlib.util.module_from_spec(SPEC)
sys.modules["organize_exports"] = organize_exports
SPEC.loader.exec_module(organize_exports)


def write_fixture(root: Path) -> None:
    with (root / "assets.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "layout": "hot_update",
                "package": "CharacterPrefab",
                "bundle_hash": "abc",
                "bundle_mode": "tail16_xor_unityfs",
                "source": r"E:\game\XzyLauncher_Data\yoo\CharacterPrefab\BundleFiles\ab\abc\__data",
                "type": "Texture2D",
                "path_id": "1",
                "asset_name": "Hero_Icon",
                "category": "textures",
                "output": r"assets\textures\Hero_Icon.png",
                "status": "exported_png",
                "manifest_reference": "ref",
                "manifest_match": "referenced",
            }
        )
        writer.writerow(
            {
                "layout": "streaming_assets",
                "package": "Voice",
                "bundle_hash": "def",
                "bundle_mode": "plain_unityfs",
                "source": r"E:\game\XzyLauncher_Data\StreamingAssets\yoo\Voice\voice.bundle",
                "type": "AudioClip",
                "path_id": "2",
                "asset_name": "Role_Voice",
                "category": "audio",
                "output": r"assets\audio\Role_Voice.wav",
                "status": "exported_audio_sample",
                "manifest_reference": "",
                "manifest_match": "",
            }
        )

    with (root / "bundles.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "layout": "hot_update",
                "package": "CharacterPrefab",
                "bundle_hash": "abc",
                "mode": "tail16_xor_unityfs",
                "source": "bundle-a",
                "length": "123",
                "raw_head": "00",
                "decoded_head": "01",
                "manifest_reference": "ref",
                "manifest_match": "referenced",
            }
        )

    table_root = root / "bin_probe" / "table_bin_probe_v6_named"
    tables_json_root = table_root / "tables_json"
    (tables_json_root / "raw" / "hot_update" / "Packet" / "abc").mkdir(parents=True)
    (tables_json_root / "raw" / "hot_update" / "Packet" / "abc" / "00000_deadbeef.bin.json").write_text(
        json.dumps(
            [
                {"Id": 1, "CharacterId": 1, "Name": "S1", "Cd": 3.0},
                {"Id": 2, "CharacterId": 1, "Name": "S2", "Cd": 8.0},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (tables_json_root / "raw" / "hot_update" / "Packet" / "abc" / "00001_facefeed.bin.json").write_text(
        json.dumps(
            [{"RoleId": 1, "Name": "Beta", "Cost": 2000}],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (tables_json_root / "raw" / "hot_update" / "Packet" / "abc" / "00002_feedcafe.bin.json").write_text(
        json.dumps(
            [{"Id": 1, "Title": "Banner Title", "Link": "https://example.invalid/banner"}],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (tables_json_root / "raw" / "hot_update" / "Packet" / "abc" / "00003_cafebabe.bin.json").write_text(
        json.dumps(
            [{"Id": 1, "Title": "Daily Task", "Reward": 100}],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (tables_json_root / "raw" / "hot_update" / "Packet" / "abc" / "00004_0badf00d.bin.json").write_text(
        json.dumps(
            [{"Id": 1, "Name": "Skill Group A", "Level": 3}],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with (table_root / "table_bins.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "rel_path",
                "entry_index",
                "file_id_hex",
                "bundle_hash",
                "packet_asset_name",
                "packet_asset_path",
                "size",
                "status",
                "row_count",
                "column_count",
                "types",
                "consumed",
                "table_name",
                "match_status",
                "field_names",
                "candidate_tables",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "rel_path": r"raw\hot_update\Packet\abc\00000_deadbeef.bin",
                "entry_index": "00000",
                "file_id_hex": "deadbeef",
                "bundle_hash": "abc",
                "packet_asset_name": "GameTables",
                "packet_asset_path": "Assets/GameData/Packets/GameTables.p",
                "size": "100",
                "status": "parsed",
                "row_count": "2",
                "column_count": "4",
                "types": "uint|uint|string|float",
                "consumed": "100",
                "table_name": "TableAmmoIndex",
                "match_status": "unique_signature",
                "field_names": "Id|CharacterId|Name|Cd",
                "candidate_tables": "TableAmmoIndex",
                "error": "",
            }
        )
        writer.writerow(
            {
                "rel_path": r"raw\hot_update\Packet\abc\00001_facefeed.bin",
                "entry_index": "00001",
                "file_id_hex": "facefeed",
                "bundle_hash": "abc",
                "packet_asset_name": "UiTables",
                "packet_asset_path": "Assets/GameData/Packets/UiTables.p",
                "size": "120",
                "status": "parsed",
                "row_count": "1",
                "column_count": "3",
                "types": "uint|string|uint",
                "consumed": "120",
                "table_name": "UiTableRole",
                "match_status": "unique_signature",
                "field_names": "RoleId|Name|Cost",
                "candidate_tables": "UiTableRole",
                "error": "",
            }
        )
        writer.writerow(
            {
                "rel_path": r"raw\hot_update\Packet\abc\00002_feedcafe.bin",
                "entry_index": "00002",
                "file_id_hex": "feedcafe",
                "bundle_hash": "abc",
                "packet_asset_name": "UiTables",
                "packet_asset_path": "Assets/GameData/Packets/UiTables.p",
                "size": "140",
                "status": "parsed",
                "row_count": "1",
                "column_count": "3",
                "types": "uint|string|string",
                "consumed": "140",
                "table_name": "UiTableJumpAdBanner",
                "match_status": "unique_signature",
                "field_names": "Id|Title|Link",
                "candidate_tables": "UiTableJumpAdBanner",
                "error": "",
            }
        )
        writer.writerow(
            {
                "rel_path": r"raw\hot_update\Packet\abc\00003_cafebabe.bin",
                "entry_index": "00003",
                "file_id_hex": "cafebabe",
                "bundle_hash": "abc",
                "packet_asset_name": "UiTables",
                "packet_asset_path": "Assets/GameData/Packets/UiTables.p",
                "size": "150",
                "status": "parsed",
                "row_count": "1",
                "column_count": "3",
                "types": "uint|string|uint",
                "consumed": "150",
                "table_name": "UiTableActivityDailyTask",
                "match_status": "unique_signature",
                "field_names": "Id|Title|Reward",
                "candidate_tables": "UiTableActivityDailyTask",
                "error": "",
            }
        )
        writer.writerow(
            {
                "rel_path": r"raw\hot_update\Packet\abc\00004_0badf00d.bin",
                "entry_index": "00004",
                "file_id_hex": "0badf00d",
                "bundle_hash": "abc",
                "packet_asset_name": "UiTables",
                "packet_asset_path": "Assets/GameData/Packets/UiTables.p",
                "size": "160",
                "status": "parsed",
                "row_count": "1",
                "column_count": "3",
                "types": "uint|string|uint",
                "consumed": "160",
                "table_name": "UiTableGroupSkill",
                "match_status": "unique_signature",
                "field_names": "Id|Name|Level",
                "candidate_tables": "UiTableGroupSkill",
                "error": "",
            }
        )

    table_texts = root / "table_texts_all"
    table_texts.mkdir(parents=True)
    (table_texts / "table_texts.csv").write_text(
        "\n".join(
            [
                "table_name,match_status,packet_asset_name,packet_asset_path,rel_path,row_index,row_id,field_name,text_kind,text",
                "TableAmmoIndex,unique_signature,GameTables,Assets/GameData/Packets/GameTables.p,raw/hot_update/Packet/abc/00000_deadbeef.bin,0,1,Name,name,S1",
                "UiTableRole,unique_signature,UiTables,Assets/GameData/Packets/UiTables.p,raw/hot_update/Packet/abc/00001_facefeed.bin,0,1,Name,name,Beta",
                "UiTableJumpAdBanner,unique_signature,UiTables,Assets/GameData/Packets/UiTables.p,raw/hot_update/Packet/abc/00002_feedcafe.bin,0,1,Title,title,Banner Title",
                "UiTableActivityDailyTask,unique_signature,UiTables,Assets/GameData/Packets/UiTables.p,raw/hot_update/Packet/abc/00003_cafebabe.bin,0,1,Title,title,Daily Task",
                "UiTableGroupSkill,unique_signature,UiTables,Assets/GameData/Packets/UiTables.p,raw/hot_update/Packet/abc/00004_0badf00d.bin,0,1,Name,name,Skill Group A",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )


class OrganizeExportsTests(unittest.TestCase):
    def test_generates_business_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            out = root / "organized"
            summary = organize_exports.main(
                [
                    "--input",
                    str(root),
                    "--out",
                    str(out),
                    "--table-probe",
                    str(root / "bin_probe" / "table_bin_probe_v6_named"),
                    "--table-texts",
                    str(root / "table_texts_all"),
                    "--write-json",
                ]
            )
            self.assertEqual(summary, 0)

            characters = out / "characters" / "tables.csv"
            skills = out / "skills" / "tables.csv"
            ui = out / "ui" / "texts.csv"
            character_basic = out / "characters" / "character_basic.csv"
            skill_cooldowns = out / "skills" / "skill_cooldowns.csv"
            activity_texts = out / "ui" / "activity_texts.csv"
            banner_texts = out / "ui" / "banner_texts.csv"
            skill_groups = out / "skills" / "skill_groups.csv"
            review = out / "review" / "tables.csv"
            summary_json = out / "_index" / "summary.json"
            browse_readme = out / "README.md"

            self.assertTrue(characters.exists())
            self.assertTrue(skills.exists())
            self.assertTrue(ui.exists())
            self.assertTrue(character_basic.exists())
            self.assertTrue(skill_cooldowns.exists())
            self.assertTrue(activity_texts.exists())
            self.assertTrue(banner_texts.exists())
            self.assertTrue(skill_groups.exists())
            self.assertTrue(review.exists())
            self.assertTrue(summary_json.exists())
            self.assertTrue(browse_readme.exists())

            with characters.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "UiTableRole" for row in rows))

            with skills.open("r", encoding="utf-8-sig", newline="") as file:
                skill_rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "TableAmmoIndex" for row in skill_rows))

            with ui.open("r", encoding="utf-8-sig", newline="") as file:
                text_rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "UiTableJumpAdBanner" for row in text_rows))

            with character_basic.open("r", encoding="utf-8-sig", newline="") as file:
                character_basic_rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "UiTableRole" for row in character_basic_rows))

            with skill_cooldowns.open("r", encoding="utf-8-sig", newline="") as file:
                skill_cooldown_rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "TableAmmoIndex" for row in skill_cooldown_rows))

            with activity_texts.open("r", encoding="utf-8-sig", newline="") as file:
                activity_rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "UiTableActivityDailyTask" for row in activity_rows))

            with banner_texts.open("r", encoding="utf-8-sig", newline="") as file:
                banner_rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "UiTableJumpAdBanner" for row in banner_rows))

            with skill_groups.open("r", encoding="utf-8-sig", newline="") as file:
                skill_group_rows = list(csv.DictReader(file))
            self.assertTrue(any(row["table_name"] == "UiTableGroupSkill" for row in skill_group_rows))

            payload = json.loads(summary_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["assets"]["rows"], 2)
            self.assertEqual(payload["tables"]["rows"], 5)
            self.assertEqual(payload["tables"]["selected_text_rows"], 5)
            browse_text = browse_readme.read_text(encoding="utf-8")
            self.assertIn("First Open", browse_text)
            self.assertIn("Bucket Map", browse_text)
            self.assertIn("characters/tables.csv", browse_text)


if __name__ == "__main__":
    unittest.main()
