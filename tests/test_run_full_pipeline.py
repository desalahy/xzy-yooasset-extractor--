from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "run_full_pipeline.py"
SPEC = importlib.util.spec_from_file_location("run_full_pipeline", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
run_full_pipeline = importlib.util.module_from_spec(SPEC)
sys.modules["run_full_pipeline"] = run_full_pipeline
SPEC.loader.exec_module(run_full_pipeline)


FAKE_PACKET_KEY = "0123456789abcdef0123456789abcdef"


class RunFullPipelineTests(unittest.TestCase):
    def test_progress_reporter_does_not_use_unsupported_overflow_kwarg(self) -> None:
        progress_source = (TOOL_PATH.parent.parent / "xzy_yooasset_core" / "progress.py").read_text(encoding="utf-8")
        self.assertNotIn('overflow="ellipsis"', progress_source)

    def test_build_pipeline_wires_expected_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dump_cs = Path(tmp) / "dump.cs"
            dump_cs.write_text("public struct UiTableGlobal.tData\n", encoding="utf-8")
            args = run_full_pipeline.parse_args(
                [
                    "--game-root",
                    r"E:\game",
                    "--out",
                    r"E:\out",
                    "--key-text",
                    "k",
                    "--dump-cs",
                    str(dump_cs),
                ]
            )

            steps = run_full_pipeline.build_pipeline(args)

        self.assertEqual(
            [step.name for step in steps],
            [
                "export_assets",
                "probe_packets",
                "probe_table_bins",
                "extract_table_texts_activity",
                "extract_table_texts_all",
                "probe_binary_bins",
                "export_gameplay_tables",
                "export_classified_tables",
                "organize_exports",
                "probe_string_bins",
            ],
        )
        self.assertIn("--copy-rawfiles", steps[0].command)
        self.assertEqual(steps[1].command[0], sys.executable)
        self.assertIn(str(Path(r"E:\out") / "raw"), steps[1].command)
        self.assertIn("--key-text", steps[1].command)
        self.assertIn("--dump-cs", steps[2].command)
        self.assertEqual(Path(steps[6].command[1]).name, "export_gameplay_tables.py")
        self.assertIn("--include-ui-skill", steps[6].command)
        self.assertEqual(Path(steps[7].command[1]).name, "export_classified_tables.py")
        self.assertIn("--table-texts", steps[7].command)
        self.assertIn("--table-texts", steps[8].command)

    def test_build_pipeline_reuses_existing_packet_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet_tree = Path(tmp) / "packet_extract_full_decoded"
            extracted = packet_tree / "extracted"
            extracted.mkdir(parents=True)
            (extracted / "dummy.bin").write_bytes(b"\x00")

            args = run_full_pipeline.parse_args(
                [
                    "--game-root",
                    r"E:\game",
                    "--out",
                    r"E:\out",
                    "--packet-input",
                    str(packet_tree),
                    "--skip-export",
                ]
            )

            steps = run_full_pipeline.build_pipeline(args)

        self.assertEqual(
            [step.name for step in steps],
            [
                "probe_table_bins",
                "extract_table_texts_activity",
                "extract_table_texts_all",
                "probe_binary_bins",
                "export_gameplay_tables",
                "export_classified_tables",
                "organize_exports",
                "probe_string_bins",
            ],
        )
        self.assertIn(str(extracted), steps[0].command)
        self.assertIn(str(extracted), steps[3].command)
        self.assertIn(str(extracted), steps[7].command)

    def test_build_pipeline_auto_adds_packet_key_from_resources_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "game"
            data_root = game_root / "XzyLauncher_Data"
            data_root.mkdir(parents=True)
            (data_root / "resources.assets").write_bytes(
                b"\x00_GameConfig\x00 \x00\x00\x00" + FAKE_PACKET_KEY.encode("ascii") + b"\x00"
            )
            args = run_full_pipeline.parse_args(
                [
                    "--game-root",
                    str(game_root),
                    "--out",
                    str(Path(tmp) / "out"),
                ]
            )

            packet_key = run_full_pipeline.resolve_packet_key(args)
            steps = run_full_pipeline.build_pipeline(args, packet_key)

        self.assertEqual(packet_key.value, FAKE_PACKET_KEY)
        self.assertEqual(packet_key.source, "resources.assets")
        self.assertIn("--key-text", steps[1].command)
        self.assertIn(FAKE_PACKET_KEY, steps[1].command)

    def test_manual_packet_key_takes_precedence_over_resources_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "game"
            data_root = game_root / "XzyLauncher_Data"
            data_root.mkdir(parents=True)
            (data_root / "resources.assets").write_bytes(
                b"_GameConfig\x00 \x00\x00\x00" + FAKE_PACKET_KEY.encode("ascii") + b"\x00"
            )
            args = run_full_pipeline.parse_args(
                [
                    "--game-root",
                    str(game_root),
                    "--out",
                    str(Path(tmp) / "out"),
                    "--key-text",
                    "ManualPacketKeyValue0000000000",
                ]
            )

            packet_key = run_full_pipeline.resolve_packet_key(args)
            steps = run_full_pipeline.build_pipeline(args, packet_key)

        self.assertEqual(packet_key.value, "ManualPacketKeyValue0000000000")
        self.assertEqual(packet_key.source, "key-text")
        self.assertIn("--key-text", steps[1].command)
        self.assertIn("ManualPacketKeyValue0000000000", steps[1].command)

    def test_main_writes_pipeline_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "out"

            def fake_run(command: list[str], cwd: Path) -> object:
                return type("Proc", (), {"returncode": 0})()

            with patch.object(run_full_pipeline.subprocess, "run", side_effect=fake_run):
                rc = run_full_pipeline.main(
                    [
                        "--game-root",
                        r"E:\game",
                        "--out",
                        str(out_root),
                        "--key-text",
                        "k",
                    ]
                )

            self.assertEqual(rc, 0)
            summary = json.loads((out_root / "pipeline_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "success")
            self.assertEqual(len(summary["steps"]), 10)
            self.assertTrue(summary["inputs"]["key_text_supplied"])

    def test_main_records_auto_packet_key_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "game"
            data_root = game_root / "XzyLauncher_Data"
            data_root.mkdir(parents=True)
            (data_root / "resources.assets").write_bytes(
                b"\x00_GameConfig\x00 \x00\x00\x00" + FAKE_PACKET_KEY.encode("ascii") + b"\x00"
            )
            out_root = Path(tmp) / "out"
            commands: list[list[str]] = []

            def fake_run(command: list[str], cwd: Path) -> object:
                commands.append(command)
                return type("Proc", (), {"returncode": 0})()

            with patch.object(run_full_pipeline.subprocess, "run", side_effect=fake_run):
                rc = run_full_pipeline.main(
                    [
                        "--game-root",
                        str(game_root),
                        "--out",
                        str(out_root),
                    ]
                )

            self.assertEqual(rc, 0)
            summary = json.loads((out_root / "pipeline_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "success")
            self.assertEqual(summary["inputs"]["packet_key_source"], "resources.assets")
            self.assertTrue(summary["inputs"]["packet_key_auto_discovered"])
            self.assertNotIn("packet_key_missing", summary["warnings"])
            self.assertIn("--key-text", commands[1])
            self.assertIn(FAKE_PACKET_KEY, commands[1])

    def test_main_accepts_existing_packet_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "out"
            packet_tree = Path(tmp) / "packet_extract_full_decoded"
            (packet_tree / "extracted").mkdir(parents=True)
            (packet_tree / "extracted" / "dummy.bin").write_bytes(b"\x00")

            def fake_run(command: list[str], cwd: Path) -> object:
                return type("Proc", (), {"returncode": 0})()

            with patch.object(run_full_pipeline.subprocess, "run", side_effect=fake_run):
                rc = run_full_pipeline.main(
                    [
                        "--game-root",
                        r"E:\game",
                        "--out",
                        str(out_root),
                        "--packet-input",
                        str(packet_tree),
                        "--skip-export",
                    ]
                )

            self.assertEqual(rc, 0)
            summary = json.loads((out_root / "pipeline_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "success")
            self.assertTrue(summary["inputs"]["packet_input_supplied"])
            self.assertEqual(summary["inputs"]["packet_input_resolved"], str((packet_tree / "extracted").resolve()))
            self.assertEqual(len(summary["steps"]), 8)
            self.assertNotIn("packet_key_missing", summary["warnings"])


if __name__ == "__main__":
    unittest.main()
