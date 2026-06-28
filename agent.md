# Agent Handoff

This file is for the next AI agent that continues this repository. Read it before editing code or docs.

## Mission

`xzy-yooasset-extractor` is a local research and learning tool for one Unity/YooAssets game installation layout. It extracts local YooAssets bundles, probes Packet/raw containers, parses table `.bin` files, exports text indexes, and builds classified JSON/CSV/XLSX outputs.

Repository root:

```text
<this repository root>
```

Example output root used by commands and tests:

```text
<output-root>
```

Example game root expected by the extractor:

```text
<game-root-containing-XzyLauncher_Data>
```

Do not hard-code old local paths when migrating the project.

## Hard Boundaries

- Do not commit or publish game assets, exported images, audio, models, bundles, metadata dumps, `dump.cs`, encryption keys, or decoded content from the game.
- The repository should contain code, tests, and docs only.
- Dependencies must be managed with `uv`. Do not reintroduce `requirements.txt`, `.runtime_deps`, `pip install --target`, or `--deps-dir`.
- Run Python commands as `uv run python ...`.
- Keep `uv.lock` committed for reproducibility. Keep `.venv/`, `.uv-cache/`, `.analysis_deps/`, `.analysis_tmp/`, and `.test_tmp/` ignored.
- If a directory called `.analysis_deps` remains locally, treat it as an obsolete ACL-damaged cache. Code must not use it.
- Do not claim the Python extractor writes native Unity `.prefab` files. It writes sidecar JSON and `prefab_graph.json`; Unity 2022.3 Editor reconstruction is the intended second stage.
- Do not treat every remaining `.bin` as failed decryption. Most are parsed tables or classified non-table binary payloads.

## Setup

```powershell
uv sync
uv run python xzy_yooasset_extractor.py --help
```

If uv cannot read its managed Python directory on this Windows machine:

```bat
set UV_PYTHON=<path-to-python-3.10-or-newer.exe>
uv sync
```

The batch files already set `UV_CACHE_DIR` to the project-local `.uv-cache/` and retry `uv sync` with `py -3` when uv Python discovery fails.

## Current Architecture

Core package:

- `xzy_yooasset_core/bundle.py`: bundle probing and tail-16 XOR decode.
- `xzy_yooasset_core/discovery.py`: game root, YooAssets root, package, bundle, and rawfile discovery.
- `xzy_yooasset_core/exporter.py`: UnityPy export, rawfile copying, prefab sidecar JSON, `prefab_graph.json`.
- `xzy_yooasset_core/manifest.py`: local manifest/catalog scanning and Packet manifest parsing.
- `xzy_yooasset_core/cli.py`: main extractor CLI and multiprocessing orchestration.
- `xzy_yooasset_core/progress.py`: Rich/plain progress display.

Tool chain:

1. `xzy_yooasset_extractor.py`: main YooAssets/bundle export.
2. `tools/probe_packets.py`: Packet/BattlePacket/Assembly raw container extraction.
3. `tools/probe_table_bins.py`: Packet table `.bin` parser and `dump.cs` field-name matching.
4. `tools/extract_table_texts.py`: searchable table text extraction.
5. `tools/export_gameplay_tables.py`: gameplay/character/skill/battle table export.
6. `tools/export_classified_tables.py`: remaining named table business classification.
7. `tools/probe_binary_bins.py`: non-table `.bin` fingerprint classification.
8. `tools/probe_string_bins.py`: experimental string-list probe.
9. `tools/organize_exports.py`: business-level browsing indexes.
10. `tools/run_full_pipeline.py`: one-command orchestration for the current Python pipeline.

Windows entry points:

- `run_all_windows.bat`: full pipeline.
- `run_wizard_windows.bat`: focused export/debug modes plus full pipeline modes.

## Current Verified Capabilities

The project currently supports:

- Scanning both local layouts with `--game-root`:
  - `XzyLauncher_Data/yoo/<Package>/BundleFiles/**/__data`
  - `XzyLauncher_Data/StreamingAssets/yoo/<Package>/*.bundle`
- Detecting `plain_unityfs`, `tail16_xor_unityfs`, `tail16_xor_non_unity`, and `unknown`.
- Decoding the tail-16 XOR UnityFS bundle format.
- Exporting common Unity objects through UnityPy: PNG textures/sprites, audio samples, raw/text objects, prefab sidecar JSON.
- Copying `.rawfile` payloads with `--copy-rawfiles`.
- Extracting Packet/raw containers with AES-CBC support.
- Mapping Packet hash folders back to logical names such as `GameTables` and `UiTables` via manifest parsing.
- Parsing table `.bin` files and applying field names from Il2CppDumper `dump.cs`.
- Extracting searchable CJK table text.
- Exporting gameplay tables and classified named tables to JSON, CSV, and optional XLSX.
- Classifying residual non-table `.bin` payloads into categories such as `animation_like`, `animation_state_skeleton`, `unity_yaml_meta`, `collision_like`, `string_list`, `binary_with_strings`, and `tiny_placeholder`.

Historical verification snapshot from one local sample output:

- `gameplay_tables`: 39 tables, 16130 rows.
- `classified_tables`: 118 tables, 12439 rows.
- Packet line from prior validated run: 347 packet/raw containers parsed, 19824 internal entries extracted, no remaining `.encrypted` when not using `--strict-decode`.
- Table probe line from prior validated run: 906 `.bin` files scanned; roughly half parsed as tables, and most table fields can be named from `dump.cs`.

Treat these as historical evidence, not guaranteed current output after code changes or different game data.

## Current Limitations

- Native Unity `.prefab` generation is not implemented in Python. The stable route is Unity 2022.3 Editor reconstruction from sidecar manifests.
- Mesh/FBX export is not yet AssetStudio-equivalent. The current model path mainly inventories Unity objects, textures, materials, and prefab graph data.
- Ambiguous table signatures are intentionally not force-named. Do not hard guess names without more evidence.
- Some binary formats are classified but not structurally decoded yet, especially animation/collision-like payloads.
- Static manifest matching is useful evidence, not runtime truth. `not_found` does not prove unused.
- `.analysis_deps/` may exist locally with broken ACLs. It is ignored and obsolete.

## Verification Commands

Use these after changing code:

```powershell
uv sync
uv run python -m py_compile xzy_yooasset_extractor.py tools\export_gameplay_tables.py tools\export_classified_tables.py tools\run_full_pipeline.py tools\probe_packets.py
uv run python -m unittest tests.test_export_gameplay_tables tests.test_export_classified_tables tests.test_run_full_pipeline
uv run python -m unittest discover -s tests
```

The focused tests are faster and cover the current pipeline wiring. Full `discover` should pass before publishing.

## Suggested Next Work

1. Add a Unity 2022.3 reconstruction sample project/editor script that reads `prefab_graph.json` and writes real `.prefab`, `.mat`, `.anim`, and controller assets.
2. Improve model export fidelity by comparing AssetStudio behavior: Mesh to OBJ, Animator to FBX, MonoBehaviour to JSON.
3. Add schema-specific decoders for high-value residual `.bin` groups such as animation state, collision, and behavior payloads.
4. Improve table classification with review reports for ambiguous/no-match tables.
5. Add CI-like smoke tests that run with `uv` and synthetic data only.
6. Keep `README.md`, `docs/zh-CN.md`, `docs/project-history.md`, and `docs/project-status-and-roadmap.md` in sync after feature changes.

## Suggested Skills

- `diagnose`: use for broken exports, parser regressions, or performance problems.
- `teach`: use when updating lessons or explaining reverse-engineering concepts to the user.
- `tdd`: use for new parser behavior, table classifiers, and pipeline regressions.
- `handoff`: use before ending a long investigation so the next agent can continue without losing context.
