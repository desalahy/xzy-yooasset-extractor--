from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROBE_PATH = Path(__file__).resolve().parents[1] / "tools" / "probe_binary_bins.py"
TOOLS_PATH = PROBE_PATH.parent
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))
SPEC = importlib.util.spec_from_file_location("probe_binary_bins", PROBE_PATH)
assert SPEC is not None and SPEC.loader is not None
probe_binary_bins = importlib.util.module_from_spec(SPEC)
sys.modules["probe_binary_bins"] = probe_binary_bins
SPEC.loader.exec_module(probe_binary_bins)


class ProbeBinaryBinsTests(unittest.TestCase):
    def test_animation_packet_zero_placeholder_is_state_skeleton(self) -> None:
        category, _text, strings, error = probe_binary_bins.classify_binary(
            b"\x00" * 12,
            r"assets\raw\streaming_assets\AnimationPacket\hash\00000.bin",
        )

        self.assertEqual(category, "animation_state_skeleton")
        self.assertEqual(strings, [])
        self.assertEqual(error, "")

    def test_animation_packet_counted_low_entropy_records_are_state_skeleton(self) -> None:
        record = bytes.fromhex("00 00 01 00 00 00 00 00 00 01 00 02 02")
        data = bytes([11]) + record * 11
        category, _text, strings, error = probe_binary_bins.classify_binary(
            data,
            r"assets\raw\streaming_assets\AnimationPacket\hash\00000.bin",
        )

        self.assertEqual(category, "animation_state_skeleton")
        self.assertEqual(strings, [])
        self.assertEqual(error, "")

    def test_animation_packet_action_id_without_strings_is_state_skeleton(self) -> None:
        data = bytes.fromhex(
            "0d f4 01 04 00 00 00 00 00 00 00 00 00 00 00 00"
            "00 00 00 00 00 00 00 00 f9 01 04 00 00 00 00 00"
        )
        category, _text, strings, error = probe_binary_bins.classify_binary(
            data,
            r"assets\raw\streaming_assets\AnimationPacket\hash\00000.bin",
        )

        self.assertEqual(category, "animation_state_skeleton")
        self.assertEqual(strings, [])
        self.assertEqual(error, "")

    def test_counted_records_outside_animation_packet_remain_unknown(self) -> None:
        record = bytes.fromhex("00 00 01 00 00 00 00 00 00 01 00 02 02")
        data = bytes([11]) + record * 11
        category, _text, _strings, _error = probe_binary_bins.classify_binary(
            data,
            r"assets\raw\streaming_assets\Packet\hash\00000.bin",
        )

        self.assertEqual(category, "binary_unknown")


if __name__ == "__main__":
    unittest.main()
