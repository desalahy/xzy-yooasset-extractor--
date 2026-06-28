from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: list[str]
    required: bool
    outputs: tuple[str, ...] = ()


@dataclass
class StepResult:
    name: str
    required: bool
    command: list[str]
    outputs: list[str]
    returncode: int
    duration_seconds: float
    status: str


@dataclass(frozen=True)
class PacketKey:
    value: str
    source: str


GAMECONFIG_MARKER = b"_GameConfig"
PACKET_KEY_RE = re.compile(rb"[A-Za-z0-9+/=_-]{16,64}")
AES_KEY_LENGTHS = (32, 24, 16)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full XZY extraction and indexing pipeline.")
    parser.add_argument("--game-root", required=True, help="Game root containing XzyLauncher_Data.")
    parser.add_argument("--out", required=True, help="Output root for the full pipeline.")
    parser.add_argument("--yoo-root", default="", help="Optional direct YooAssets root. Overrides --game-root when provided.")
    parser.add_argument("--source-layout", choices=("all", "hot", "streaming"), default="all", help="YooAssets source layout to scan.")
    parser.add_argument("--workers", type=int, default=4, help="Worker processes for the main asset export.")
    parser.add_argument("--progress-every", type=int, default=1, help="Refresh the main export progress after N bundles.")
    parser.add_argument("--progress-style", choices=("bar", "lines", "none"), default="bar", help="Main export progress display style.")
    parser.add_argument("--skip-export", action="store_true", help="Reuse an existing out/raw export and skip the main asset export stage.")
    parser.add_argument("--dump-cs", default="", help="Optional Il2CppDumper dump.cs for table schema naming.")
    parser.add_argument("--key-text", default="", help="Optional packet AES key as UTF-8 text.")
    parser.add_argument("--key-hex", default="", help="Optional packet AES key as hex.")
    parser.add_argument("--iv-hex", default="", help="Optional fixed packet AES IV as hex.")
    parser.add_argument("--packet-name", default="", help="Optional fixed Packet logical name for IV derivation.")
    parser.add_argument("--packet-input", default="", help="Optional existing decoded packet tree. When set, skip probe_packets and reuse this tree (or its extracted/ child) for later probes.")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def command_for(script_name: str) -> list[str]:
    return [sys.executable, str(PROJECT_ROOT / script_name)]


def add_if_present(command: list[str], flag: str, value: str) -> None:
    if value:
        command.extend([flag, value])


def resolve_packet_input_root(packet_input: str) -> Path | None:
    if not packet_input:
        return None

    root = Path(packet_input).expanduser().resolve()
    if not root.exists():
        return None

    if root.is_file():
        root = root.parent

    extracted = root / "extracted"
    if extracted.is_dir():
        return extracted.resolve()
    return root


def resources_assets_path(game_root: str) -> Path:
    return Path(game_root).expanduser().resolve() / "XzyLauncher_Data" / "resources.assets"


def find_packet_key_in_resources_assets(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""

    data = path.read_bytes()
    marker_at = data.find(GAMECONFIG_MARKER)
    if marker_at < 0:
        return ""

    window = data[marker_at : marker_at + 4096]
    candidates: list[str] = []
    for match in PACKET_KEY_RE.finditer(window):
        value = match.group(0).decode("ascii", errors="ignore")
        if value in {"_GameConfig", "YooAssetSettings"}:
            continue
        if len(value) in AES_KEY_LENGTHS:
            candidates.append(value)

    for key_length in AES_KEY_LENGTHS:
        for candidate in candidates:
            if len(candidate) == key_length:
                return candidate
    return ""


def resolve_packet_key(args: argparse.Namespace) -> PacketKey:
    if args.key_text:
        return PacketKey(args.key_text, "key-text")
    if args.key_hex:
        return PacketKey(args.key_hex, "key-hex")

    value = find_packet_key_in_resources_assets(resources_assets_path(args.game_root))
    if value:
        return PacketKey(value, "resources.assets")
    return PacketKey("", "")


def build_pipeline(args: argparse.Namespace, packet_key: PacketKey | None = None) -> list[PipelineStep]:
    if packet_key is None:
        packet_key = resolve_packet_key(args)

    out_root = Path(args.out).expanduser().resolve()
    packet_out = out_root / "bin_probe" / "packet_extract_full_decoded"
    table_out = out_root / "bin_probe" / "table_bin_probe_named"
    activity_text_out = out_root / "table_texts_activity"
    all_text_out = out_root / "table_texts_all"
    binary_out = out_root / "bin_probe" / "binary_probe_named"
    string_out = out_root / "bin_probe" / "string_probe_named"
    gameplay_out = out_root / "gameplay_tables"
    classified_out = out_root / "classified_tables"
    organized_out = out_root / "organized"
    packet_source_root = resolve_packet_input_root(args.packet_input) or (packet_out / "extracted")

    export_cmd = command_for("xzy_yooasset_extractor.py")
    export_cmd.extend(["--game-root", args.game_root, "--source-layout", args.source_layout, "--out", str(out_root), "--limit", "0", "--copy-rawfiles", "--execute"])
    export_cmd.extend(["--workers", str(args.workers), "--progress-every", str(args.progress_every), "--progress-style", args.progress_style])
    add_if_present(export_cmd, "--yoo-root", args.yoo_root)

    table_cmd = command_for("tools/probe_table_bins.py")
    table_cmd.extend(["--input", str(packet_source_root), "--out", str(table_out), "--sample-rows", "3", "--export-json", "--game-root", args.game_root])
    dump_cs = Path(args.dump_cs).expanduser() if args.dump_cs else None
    if dump_cs and dump_cs.exists():
        table_cmd.extend(["--dump-cs", str(dump_cs.resolve())])

    activity_text_cmd = command_for("tools/extract_table_texts.py")
    activity_text_cmd.extend(
        [
            "--table-probe",
            str(table_out),
            "--out",
            str(activity_text_out),
            "--table-regex",
            "UiTableActivity|UiTableJumpAdBanner|UiTableGlobal",
            "--field-regex",
            "Comment|Description|Title|Name|Text|StringValue|Choice",
            "--export-json",
        ]
    )

    all_text_cmd = command_for("tools/extract_table_texts.py")
    all_text_cmd.extend(["--table-probe", str(table_out), "--out", str(all_text_out), "--only-cjk"])

    binary_cmd = command_for("tools/probe_binary_bins.py")
    binary_cmd.extend(["--input", str(packet_source_root), "--out", str(binary_out), "--table-report", str(table_out / "table_bins.csv"), "--game-root", args.game_root])

    gameplay_cmd = command_for("tools/export_gameplay_tables.py")
    gameplay_cmd.extend(["--table-probe", str(table_out), "--out", str(gameplay_out), "--include-ui-skill", "--xlsx"])

    classified_cmd = command_for("tools/export_classified_tables.py")
    classified_cmd.extend(["--table-probe", str(table_out), "--table-texts", str(all_text_out), "--out", str(classified_out), "--xlsx"])

    organize_cmd = command_for("tools/organize_exports.py")
    organize_cmd.extend(
        [
            "--input",
            str(out_root),
            "--out",
            str(organized_out),
            "--table-probe",
            str(table_out),
            "--table-texts",
            str(all_text_out),
            "--binary-probe",
            str(binary_out),
        ]
    )

    string_cmd = command_for("tools/probe_string_bins.py")
    string_cmd.extend(["--input", str(packet_source_root), "--out", str(string_out), "--game-root", args.game_root, "--export-json"])

    steps: list[PipelineStep] = []
    if not args.skip_export:
        steps.append(
            PipelineStep(
                "export_assets",
                export_cmd,
                True,
                (str(out_root / "assets.csv"), str(out_root / "bundles.csv"), str(out_root / "summary.json")),
            )
        )

    if not args.packet_input:
        packet_cmd = command_for("tools/probe_packets.py")
        packet_cmd.extend(["--input", str(out_root / "raw"), "--out", str(packet_out), "--game-root", args.game_root, "--extract", "--sample-entries", "3"])
        add_if_present(packet_cmd, "--yoo-root", args.yoo_root)
        if packet_key.source == "key-hex":
            add_if_present(packet_cmd, "--key-hex", packet_key.value)
        else:
            add_if_present(packet_cmd, "--key-text", packet_key.value)
        add_if_present(packet_cmd, "--iv-hex", args.iv_hex)
        add_if_present(packet_cmd, "--packet-name", args.packet_name)
        steps.append(PipelineStep("probe_packets", packet_cmd, True, (str(packet_out / "packets.csv"), str(packet_out / "packet_entries.csv"), str(packet_out / "summary.json"))))

    steps.extend(
        [
        PipelineStep("probe_table_bins", table_cmd, True, (str(table_out / "table_bins.csv"), str(table_out / "tables_json"), str(table_out / "summary.json"))),
        PipelineStep("extract_table_texts_activity", activity_text_cmd, True, (str(activity_text_out / "table_texts.csv"), str(activity_text_out / "table_texts.json"))),
        PipelineStep("extract_table_texts_all", all_text_cmd, True, (str(all_text_out / "table_texts.csv"), str(all_text_out / "summary.json"))),
        PipelineStep("probe_binary_bins", binary_cmd, True, (str(binary_out / "binary_bins.csv"), str(binary_out / "summary.json"))),
        PipelineStep("export_gameplay_tables", gameplay_cmd, True, (str(gameplay_out / "tables.csv"), str(gameplay_out / "summary.json"))),
        PipelineStep("export_classified_tables", classified_cmd, True, (str(classified_out / "tables.csv"), str(classified_out / "summary.json"))),
        PipelineStep("organize_exports", organize_cmd, True, (str(organized_out), str(organized_out / "README.md"))),
        PipelineStep("probe_string_bins", string_cmd, False, (str(string_out / "string_bins.csv"), str(string_out / "summary.json"))),
    ]
    )

    return steps


def run_step(step: PipelineStep) -> StepResult:
    started = time.perf_counter()
    print(f"\n=== {step.name} ===", flush=True)
    print(subprocess.list2cmdline(step.command), flush=True)
    completed = subprocess.run(step.command, cwd=PROJECT_ROOT)
    duration = time.perf_counter() - started
    status = "ok" if completed.returncode == 0 else ("soft_failed" if not step.required else "failed")
    print(f"{step.name}: exit={completed.returncode} duration={duration:.1f}s", flush=True)
    return StepResult(
        name=step.name,
        required=step.required,
        command=step.command,
        outputs=list(step.outputs),
        returncode=completed.returncode,
        duration_seconds=round(duration, 3),
        status=status,
    )


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out_root = Path(args.out).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    packet_input_root = resolve_packet_input_root(args.packet_input)
    packet_key = resolve_packet_key(args)
    warnings: list[str] = []
    if args.packet_input and packet_input_root is None:
        warnings.append(f"packet_input_missing:{Path(args.packet_input).expanduser().resolve()}")
        finished_at = iso_now()
        payload = {
            "status": "failed",
            "failed_step": "preflight",
            "started_at": iso_now(),
            "finished_at": finished_at,
            "game_root": str(Path(args.game_root).expanduser().resolve()),
            "out_root": str(out_root),
            "yoo_root": str(Path(args.yoo_root).expanduser().resolve()) if args.yoo_root else "",
            "source_layout": args.source_layout,
            "inputs": {
                "dump_cs": str(Path(args.dump_cs).expanduser().resolve()) if args.dump_cs else "",
                "key_text_supplied": bool(args.key_text),
                "key_hex_supplied": bool(args.key_hex),
                "packet_key_auto_discovered": packet_key.source == "resources.assets",
                "packet_key_source": packet_key.source,
                "iv_hex_supplied": bool(args.iv_hex),
                "packet_name_supplied": bool(args.packet_name),
                "packet_input_supplied": True,
                "packet_input": str(Path(args.packet_input).expanduser().resolve()),
                "packet_input_resolved": "",
                "skip_export": bool(args.skip_export),
            },
            "warnings": warnings,
            "steps": [],
        }
        write_summary(out_root / "pipeline_summary.json", payload)
        print(f"Missing packet input: {args.packet_input}", flush=True)
        return 2

    if args.skip_export and packet_input_root is None:
        raw_root = out_root / "raw"
        if not raw_root.exists():
            warnings.append(f"raw_missing_for_skip_export:{raw_root}")
            finished_at = iso_now()
            payload = {
                "status": "failed",
                "failed_step": "preflight",
                "started_at": iso_now(),
                "finished_at": finished_at,
                "game_root": str(Path(args.game_root).expanduser().resolve()),
                "out_root": str(out_root),
                "yoo_root": str(Path(args.yoo_root).expanduser().resolve()) if args.yoo_root else "",
                "source_layout": args.source_layout,
                "inputs": {
                    "dump_cs": str(Path(args.dump_cs).expanduser().resolve()) if args.dump_cs else "",
                    "key_text_supplied": bool(args.key_text),
                    "key_hex_supplied": bool(args.key_hex),
                    "packet_key_auto_discovered": packet_key.source == "resources.assets",
                    "packet_key_source": packet_key.source,
                    "iv_hex_supplied": bool(args.iv_hex),
                    "packet_name_supplied": bool(args.packet_name),
                    "packet_input_supplied": bool(args.packet_input),
                    "packet_input": str(Path(args.packet_input).expanduser().resolve()) if args.packet_input else "",
                    "packet_input_resolved": str(packet_input_root) if packet_input_root else "",
                    "skip_export": True,
                },
                "warnings": warnings,
                "steps": [],
            }
            write_summary(out_root / "pipeline_summary.json", payload)
            print(f"Missing required export cache: {raw_root}", flush=True)
            return 2

    steps = build_pipeline(args, packet_key)
    step_results: list[StepResult] = []
    started_at = iso_now()
    status = "success"
    failed_step = ""

    optional_dump_cs = Path(args.dump_cs).expanduser().resolve() if args.dump_cs else None
    if args.dump_cs and not optional_dump_cs.exists():
        warnings.append(f"dump_cs_missing:{optional_dump_cs}")
    if not packet_key.value and packet_input_root is None:
        warnings.append("packet_key_missing")

    for step in steps:
        result = run_step(step)
        step_results.append(result)
        if result.returncode != 0 and step.required:
            status = "failed"
            failed_step = step.name
            break

    if warnings or any(result.returncode != 0 and not result.required for result in step_results):
        if status == "success":
            status = "success_with_warnings"

    finished_at = iso_now()
    payload = {
        "status": status,
        "failed_step": failed_step,
        "started_at": started_at,
        "finished_at": finished_at,
        "game_root": str(Path(args.game_root).expanduser().resolve()),
        "out_root": str(out_root),
        "yoo_root": str(Path(args.yoo_root).expanduser().resolve()) if args.yoo_root else "",
        "source_layout": args.source_layout,
        "inputs": {
            "dump_cs": str(optional_dump_cs) if optional_dump_cs else "",
            "key_text_supplied": bool(args.key_text),
            "key_hex_supplied": bool(args.key_hex),
            "packet_key_auto_discovered": packet_key.source == "resources.assets",
            "packet_key_source": packet_key.source,
            "iv_hex_supplied": bool(args.iv_hex),
            "packet_name_supplied": bool(args.packet_name),
            "packet_input_supplied": bool(args.packet_input),
            "packet_input": str(Path(args.packet_input).expanduser().resolve()) if args.packet_input else "",
            "packet_input_resolved": str(packet_input_root) if packet_input_root else "",
            "skip_export": bool(args.skip_export),
        },
        "warnings": warnings,
        "steps": [asdict(result) for result in step_results],
    }
    write_summary(out_root / "pipeline_summary.json", payload)

    if status == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
