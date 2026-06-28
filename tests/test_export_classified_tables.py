from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "export_classified_tables.py"
SPEC = importlib.util.spec_from_file_location("export_classified_tables", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
export_classified_tables = importlib.util.module_from_spec(SPEC)
sys.modules["export_classified_tables"] = export_classified_tables
SPEC.loader.exec_module(export_classified_tables)


def write_fixture(root: Path) -> Path:
    probe = root / "table_probe"
    json_root = probe / "tables_json" / "hot_update" / "Packet" / "hash"
    json_root.mkdir(parents=True)
    rows = [
        {
            "rel_path": r"hot_update\Packet\hash\00000_item.bin",
            "status": "parsed",
            "table_name": "UiTableItem",
            "match_status": "unique_signature",
            "packet_asset_name": "UiTables",
            "packet_asset_path": "Assets/GameData/Packets/UiTables.p",
            "row_count": "1",
            "column_count": "3",
            "field_names": "ID|PropName|PropDes",
        },
        {
            "rel_path": r"hot_update\Packet\hash\00001_activity.bin",
            "status": "parsed",
            "table_name": "UiTableActivityMission",
            "match_status": "unique_signature",
            "packet_asset_name": "UiTables",
            "packet_asset_path": "Assets/GameData/Packets/UiTables.p",
            "row_count": "1",
            "column_count": "3",
            "field_names": "Id|Comment|Description",
        },
        {
            "rel_path": r"hot_update\Packet\hash\00002_damage.bin",
            "status": "parsed",
            "table_name": "TableDamageIndex",
            "match_status": "unique_signature",
            "packet_asset_name": "GameTables",
            "packet_asset_path": "Assets/GameData/Packets/GameTables.p",
            "row_count": "1",
            "column_count": "3",
            "field_names": "Id|Name|DamageRatio",
        },
    ]
    with (probe / "table_bins.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    (json_root / "00000_item.bin.json").write_text(
        json.dumps([{"ID": 1, "PropName": "Coin", "PropDes": "Money"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (json_root / "00001_activity.bin.json").write_text(
        json.dumps([{"Id": 10, "Comment": "Event", "Description": "Clear task"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (json_root / "00002_damage.bin.json").write_text(
        json.dumps([{"Id": 100, "Name": "Hit", "DamageRatio": 1.2}], ensure_ascii=False),
        encoding="utf-8",
    )

    text_dir = root / "texts"
    text_dir.mkdir()
    (text_dir / "table_texts.csv").write_text(
        "\n".join(
            [
                "table_name,field_name,text",
                "UiTableItem,PropName,Coin",
                "UiTableActivityMission,Comment,Event",
                "UiTableActivityMission,Description,Clear task",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )
    return probe


class ExportClassifiedTablesTests(unittest.TestCase):
    def test_exports_non_gameplay_business_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = write_fixture(root)
            out = root / "classified"

            rc = export_classified_tables.main(
                [
                    "--table-probe",
                    str(probe),
                    "--table-texts",
                    str(root / "texts"),
                    "--out",
                    str(out),
                ]
            )

            self.assertEqual(rc, 0)
            self.assertTrue((out / "items_economy" / "csv" / "UiTableItem.csv").exists())
            self.assertTrue((out / "activity_mission" / "json" / "UiTableActivityMission.json").exists())
            self.assertFalse((out / "gameplay" / "csv" / "TableDamageIndex.csv").exists())

            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["tables"], 2)
            self.assertEqual(summary["by_category"]["activity_mission"], 1)
            self.assertEqual(summary["by_category"]["items_economy"], 1)

            with (out / "tables.csv").open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            activity = next(row for row in rows if row["table_name"] == "UiTableActivityMission")
            self.assertEqual(activity["text_count"], "2")


if __name__ == "__main__":
    unittest.main()
