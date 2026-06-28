from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "extract_table_texts.py"
SPEC = importlib.util.spec_from_file_location("extract_table_texts", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
extract_table_texts = importlib.util.module_from_spec(SPEC)
sys.modules["extract_table_texts"] = extract_table_texts
SPEC.loader.exec_module(extract_table_texts)


def write_probe_fixture(root: Path) -> None:
    rel_path = r"assets\raw\streaming_assets\Packet\hash\00038_a4a50163.bin"
    table_json = root / "tables_json" / rel_path
    table_json = table_json.with_suffix(table_json.suffix + ".json")
    table_json.parent.mkdir(parents=True)
    table_json.write_text(
        json.dumps(
            [
                {
                    "Id": 1,
                    "Comment": "新手成长任务",
                    "Description": "<color=#FF7F00>[街机]</color>完成街机模式",
                    "StartTime": "2023-07-17 05:00:00",
                    "Banner": "lobby_adbanner_1",
                    "Choice": ["领取奖励", "close"],
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (root / "table_bins.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "rel_path",
                "table_name",
                "match_status",
                "packet_asset_name",
                "packet_asset_path",
                "row_count",
                "column_count",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "rel_path": rel_path,
                "table_name": "UiTableActivityMission",
                "match_status": "unique_signature",
                "packet_asset_name": "UiTables",
                "packet_asset_path": "Assets/GameData/Packets/UiTables.p",
                "row_count": "1",
                "column_count": "6",
            }
        )


class ExtractTableTextsTests(unittest.TestCase):
    def test_extracts_searchable_activity_text_without_dates_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_probe_fixture(root)
            args = extract_table_texts.parse_args(["--table-probe", str(root), "--out", str(root / "out")])

            records = extract_table_texts.extract_records(args)

            texts = {record.text for record in records}
            self.assertIn("新手成长任务", texts)
            self.assertIn("<color=#FF7F00>[街机]</color>完成街机模式", texts)
            self.assertIn("领取奖励", texts)
            self.assertNotIn("2023-07-17 05:00:00", texts)
            first = next(record for record in records if record.text == "新手成长任务")
            self.assertEqual(first.table_name, "UiTableActivityMission")
            self.assertEqual(first.row_id, "1")
            self.assertEqual(first.text_kind, "comment")

    def test_filters_by_table_and_field_regex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_probe_fixture(root)
            args = extract_table_texts.parse_args(
                [
                    "--table-probe",
                    str(root),
                    "--out",
                    str(root / "out"),
                    "--table-regex",
                    "Activity",
                    "--field-regex",
                    "Description",
                ]
            )

            records = extract_table_texts.extract_records(args)

            self.assertEqual([record.field_name for record in records], ["Description"])
            self.assertEqual(records[0].text_kind, "description")

    def test_writes_utf8_sig_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_probe_fixture(root)
            out = root / "out"
            args = extract_table_texts.parse_args(["--table-probe", str(root), "--out", str(out)])
            records = extract_table_texts.extract_records(args)

            extract_table_texts.write_csv(out / "table_texts.csv", records)

            with (out / "table_texts.csv").open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertTrue(any(row["text"] == "新手成长任务" for row in rows))


if __name__ == "__main__":
    unittest.main()
