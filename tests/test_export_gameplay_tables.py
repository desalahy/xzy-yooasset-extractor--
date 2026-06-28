from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "export_gameplay_tables.py"
SPEC = importlib.util.spec_from_file_location("export_gameplay_tables", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
export_gameplay_tables = importlib.util.module_from_spec(SPEC)
sys.modules["export_gameplay_tables"] = export_gameplay_tables
SPEC.loader.exec_module(export_gameplay_tables)


def write_table_probe_fixture(root: Path) -> Path:
    probe = root / "table_probe"
    tables_json = probe / "tables_json" / "hot_update" / "Packet" / "hash"
    tables_json.mkdir(parents=True)
    rows = [
        {
            "rel_path": r"hot_update\Packet\hash\00000_deadbeef.bin",
            "status": "parsed",
            "table_name": "TableAmmoIndex",
            "match_status": "unique_signature",
            "packet_asset_name": "GameTables",
            "packet_asset_path": "Assets/GameData/Packets/GameTables.p",
            "row_count": "1",
            "column_count": "4",
            "types": "uint|uint|string|float",
            "consumed": "100",
            "candidate_tables": "",
            "field_names": "Id|CharacterId|Name|Cd",
        },
        {
            "rel_path": r"hot_update\Packet\hash\00001_facefeed.bin",
            "status": "parsed",
            "table_name": "TableDamageIndex",
            "match_status": "unique_signature",
            "packet_asset_name": "GameTables",
            "packet_asset_path": "Assets/GameData/Packets/GameTables.p",
            "row_count": "1",
            "column_count": "4",
            "types": "uint|uint|string|float",
            "consumed": "120",
            "candidate_tables": "",
            "field_names": "Id|CharacterId|Name|DamageRatio",
        },
        {
            "rel_path": r"hot_update\Packet\hash\00002_cafebabe.bin",
            "status": "parsed",
            "table_name": "TableCharacterParameter",
            "match_status": "package_preferred",
            "packet_asset_name": "GameTables",
            "packet_asset_path": "Assets/GameData/Packets/GameTables.p",
            "row_count": "1",
            "column_count": "4",
            "types": "uint|uint|uint|float",
            "consumed": "140",
            "candidate_tables": "",
            "field_names": "Id|Hp|Power|Boost",
        },
    ]
    with (probe / "table_bins.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    (tables_json / "00000_deadbeef.bin.json").write_text(
        json.dumps([{"Id": 1, "CharacterId": 1, "Name": "S1", "Cd": 3.0}], ensure_ascii=False),
        encoding="utf-8",
    )
    (tables_json / "00001_facefeed.bin.json").write_text(
        json.dumps([{"Id": 10, "CharacterId": 1, "Name": "Hit", "DamageRatio": 1.25}], ensure_ascii=False),
        encoding="utf-8",
    )
    (tables_json / "00002_cafebabe.bin.json").write_text(
        json.dumps([{"Id": 1, "Hp": 2340, "Power": 300, "Boost": 85}], ensure_ascii=False),
        encoding="utf-8",
    )
    return probe


class ExportGameplayTablesTests(unittest.TestCase):
    def test_exports_standalone_gameplay_json_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = write_table_probe_fixture(root)
            out = root / "gameplay"

            result = export_gameplay_tables.main(["--table-probe", str(probe), "--out", str(out)])

            self.assertEqual(result, 0)
            self.assertTrue((out / "skills" / "cooldown" / "json" / "TableAmmoIndex.json").exists())
            self.assertTrue((out / "skills" / "damage" / "csv" / "TableDamageIndex.csv").exists())
            self.assertTrue((out / "characters" / "stats" / "json" / "TableCharacterParameter.json").exists())
            self.assertTrue((out / "tables.csv").exists())
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["tables"], 3)
            self.assertEqual(summary["rows"], 3)

            with (out / "skills" / "cooldown" / "csv" / "TableAmmoIndex.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(rows[0]["Name"], "S1")
            self.assertEqual(rows[0]["Cd"], "3.0")


if __name__ == "__main__":
    unittest.main()
