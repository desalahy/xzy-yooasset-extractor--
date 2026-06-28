# XZY YooAsset Extractor

中文-> [docs/zh-CN.md](docs/zh-CN.md).

Local research tool for inspecting and exporting Unity/YooAssets bundles that use a tail-16-byte XOR stream key.

This repository contains code and documentation only. Do not commit game files, exported images, audio, models, metadata dumps, or any other copyrighted assets.

## Status

This project is a practical extractor built from one local game installation layout. It is useful for:

- local asset inventory
- Unity bundle inspection
- YooAssets package research
- reproducible notes for the tail-key XOR format

It is not a universal Unity extractor and it does not download missing bundles from any server.

## Features

- Scans both local YooAssets layouts when `--game-root` is used:
  - hot-update layout: `XzyLauncher_Data/yoo/<Package>/BundleFiles/**/__data`
  - built-in StreamingAssets layout: `XzyLauncher_Data/StreamingAssets/yoo/<Package>/*.bundle`
- Detects bundle modes:
  - `plain_unityfs`
  - `tail16_xor_unityfs`
  - `tail16_xor_non_unity`
  - `unknown`
- Decrypts bundles that store a 16-byte XOR key at the end of the file.
- Exports common Unity objects through UnityPy:
  - `Texture2D` and `Sprite` to PNG
  - `AudioClip` samples
  - selected raw/text objects
- Optionally copies non-Unity `.rawfile` payloads with `--copy-rawfiles`.
- Inspects and extracts Packet/BattlePacket/Assembly raw containers with `tools/probe_packets.py`.
- Parses Packet table `.bin` payloads and exports searchable table/UI text indexes.
- Exports gameplay, battle, character, skill, ammo, bullet, damage, buff, talent, and timeline tables as standalone JSON plus Excel-readable CSV files.
- Builds business-level indexes with `tools/organize_exports.py` so characters, skills, UI, audio, and visual assets are easier to browse.
- Fingerprints remaining packet `.bin` payloads with `tools/probe_binary_bins.py`, including no-string `AnimationPacket` state skeletons.
- Filters export by output category (`ui`, `bgm`, `audio`, `models`, `effects`, and more) or by Unity object type.
- Can process bundles in multiple worker processes with `--workers`.
- Shows a real progress display with total bundle count, percentage, elapsed time, ETA, asset row count, and error count.
- Provides a Windows wizard batch file for choosing the game folder, output folder, and export mode without editing command text.
- Scans local manifest/catalog-like files and records static reference evidence, so exported rows can be compared with local manifest/catalog strings.
- Writes reproducible indexes:
  - `package_report.csv`
  - `bundles.csv`
  - `assets.csv`
  - `manifest_refs.csv`
  - `errors.json`
  - `summary.json`

## Requirements

- Python 3.10 or newer
- uv

Runtime dependencies are declared in `pyproject.toml` and managed by uv:

```bash
uv sync
```

If uv cannot read its managed Python directory on your machine, point uv at an existing Python interpreter first:

```bat
set UV_PYTHON=D:\Python\python.exe
uv sync
```

Run every Python command through uv:

```bash
uv run python xzy_yooasset_extractor.py --help
```

## Project Layout

| Path | Purpose |
| --- | --- |
| `agent.md` | Handoff notes for the next AI agent continuing this repository. |
| `xzy_yooasset_extractor.py` | Backward-compatible CLI entry point. Keep running commands through this file. |
| `xzy_yooasset_core/cli.py` | Argument parsing and the main orchestration loop. |
| `xzy_yooasset_core/discovery.py` | Finds YooAssets roots, package folders, `.bundle`, `__data`, and `.rawfile` candidates. |
| `xzy_yooasset_core/bundle.py` | Bundle probing, tail-16 XOR decoding, and bundle mode classification. |
| `xzy_yooasset_core/exporter.py` | UnityPy object export, output path allocation, and rawfile copying. |
| `xzy_yooasset_core/manifest.py` | Manifest/catalog static string scan and reference matching. |
| `xzy_yooasset_core/models.py` | Shared dataclasses used by scanner, exporter, and CLI. |
| `xzy_yooasset_core/constants.py` | CSV schemas, category names, and static suffix lists. |
| `xzy_yooasset_core/progress.py` | Console progress bar and line progress reporter. |
| `xzy_yooasset_core/utils.py` | Small path, CSV, and string helpers. |
| `tools/probe_packets.py` | Probes and extracts non-UnityFS Packet/BattlePacket/Assembly raw containers. |
| `tools/probe_table_bins.py` | Parses decoded Packet table `.bin` files into CSV previews and optional JSON rows. |
| `tools/extract_table_texts.py` | Builds searchable text CSV/JSON indexes from parsed table JSON rows. |
| `tools/export_gameplay_tables.py` | Exports parsed gameplay/battle tables into standalone JSON and Excel-readable CSV files. |
| `tools/export_classified_tables.py` | Exports the remaining named tables into item, activity, shop, match, system, visual, and review buckets. |
| `tools/organize_exports.py` | Builds business-level indexes across characters, skills, UI, audio, visual, packets, and review buckets. |
| `tools/probe_binary_bins.py` | Classifies remaining non-table `.bin` payloads by lightweight binary fingerprints. |
| `tools/probe_string_bins.py` | Experimental 7-bit length-prefixed UTF-8 string-list probe. |
| `docs/project-history.md` | Historical context, decisions, pitfalls, and constraints that should not be lost. |
| `docs/project-status-and-roadmap.md` | Human-readable project status and future development plan. |
| `tests/` | Unit tests with synthetic bundles; no real game files are required. |

## Quick Start

On Windows, the simplest entry point for the full pipeline is:

```bat
run_all_windows.bat
```

It opens folder pickers for the game root and output folder, then runs export, packet probe, table text extraction, gameplay table export, binary probe, string probe, and organize in one pass. Use `run_wizard_windows.bat` for focused export/debug runs; choose mode 8 in that wizard for the full chain.
If you already have a previous export root with `raw/`, `assets.csv`, and `bundles.csv`, choose mode 9 in the wizard to reuse that cache and skip the main export stage.

List available YooAssets packages:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --list-packages
```

Dry-run two Icon bundles:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --limit 2
```

Export UI-related packages:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon,Main,Spine ^
  --categories ui ^
  --out "E:\XZY\UI" ^
  --limit 0 ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar
```

Export BGM only:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Bgm ^
  --categories bgm ^
  --types AudioClip ^
  --out "E:\XZY\BGM" ^
  --limit 0 ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar
```

Export sound effects and voice clips:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Se,Voice ^
  --categories audio ^
  --types AudioClip ^
  --out "E:\XZY\Audio" ^
  --limit 0 ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar
```

Export model-related objects:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages CharacterMesh,Art3D ^
  --categories models,materials,textures ^
  --out "E:\XZY\Models" ^
  --limit 0 ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar
```

Export effect-related objects:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages BattlePacket,AnimationPacket,CharacterPerformance ^
  --categories effects,animation,materials,textures,prefabs,raw ^
  --out "E:\XZY\Effects" ^
  --limit 0 ^
  --copy-rawfiles ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar
```

Export every local package from both local YooAssets sources:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --out "E:\XZY\AllAssets" ^
  --limit 0 ^
  --copy-rawfiles ^
  --execute ^
  --workers 4 ^
  --progress-every 1 ^
  --progress-style bar
```

`--workers 4` processes bundle classification/export in four worker processes. Start with `--workers 4`; try `6` or `8` only if your disk and CPU still have headroom. Too many workers can slow the run down because UnityPy export and image/audio writes compete for disk I/O.

`--progress-style bar` shows a console progress bar with percentage, elapsed time, ETA, asset count, and error count. `--progress-every 1` refreshes it after every bundle. Use `--progress-style lines` if you want one log line per update, or `--progress-every 0` to disable progress output. These options do not change exported content.

For a full bundle-mode inventory without Unity object export:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --out "E:\XZY\BundleIndex" ^
  --limit 0 ^
  --no-export ^
  --execute ^
  --progress-every 10 ^
  --progress-style lines
```

Classify/decrypt bundles without Unity object export:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --no-export ^
  --execute
```

Save decrypted UnityFS bundles as well:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --keep-bundles ^
  --execute
```

## Windows Batch Examples

The recommended Windows entry points are:

- `run_all_windows.bat` for the full pipeline
- `run_wizard_windows.bat` for focused export/debug runs

The `examples/` directory also contains double-clickable batch files. They now `cd` back to the project root before running, so they can find `xzy_yooasset_extractor.py` even when launched from inside `examples/`. Edit `GAME_ROOT`, `OUT_DIR`, and optionally `WORKERS` inside each file before running:

| File | Purpose |
| --- | --- |
| `run_wizard_windows.bat` | Interactive folder and mode selector. |
| `run_all_windows.bat` | Interactive one-click full pipeline: export, packet probe, table text extraction, binary probe, organize. |
| `examples/extract_all_windows.bat` | Export all local packages with bundle files. |
| `examples/extract_ui_windows.bat` | Export UI images. |
| `examples/extract_bgm_windows.bat` | Export BGM AudioClip samples. |
| `examples/extract_models_windows.bat` | Export model-related objects, materials, and textures. |
| `examples/extract_effects_windows.bat` | Export effect-related objects, animation data, materials, textures, prefabs, and rawfile payloads. |

## Output Layout

```text
out/
  package_report.csv
  bundles.csv
  assets.csv
  manifest_refs.csv
  errors.json
  summary.json
  assets/
    ui/
      hot_update/Icon/<bundle_hash>/*.png
      streaming_assets/Icon/<bundle_hash>/*.png
    audio/
    bgm/
    models/
    effects/
    animation/
    prefabs/
    text/
    textures/
    raw/
    prefabs/<layout>/<package>/<bundle_hash>/prefab_graph.json
```

`assets.csv` is the main lookup table. Each row includes source layout, package name, bundle hash, bundle mode, Unity object type, `path_id`, original asset name, output category, output path, export status, and local manifest reference evidence.

`prefab_graph.json` is the bundle-level manifest for Unity reconstruction. It records prefab-tree nodes, component references, parent/child links, mesh/material/animation anchors, and the bundle identity needed by a Unity 2022.3 Editor project to rebuild a real `.prefab`.

`prefab_graph.json` is meant for the Unity reconstruction step, not for direct use as the final asset. The Unity 2022.3 Editor project consumes it and writes the actual `.prefab` files.

The extra `hot_update` / `streaming_assets` directory level prevents collisions when the same package or hash-like name appears in both YooAssets roots.

## Manifest Reference Check

The extractor performs a static scan of local manifest/catalog-like files by default. This helps answer: "is this bundle or object mentioned by the local manifest/catalog data?"

It reads `ManifestFiles/**/*` from the hot-update layout and `.bytes`, `.json`, `.hash`, `.version` files from the StreamingAssets layout.

New columns:

| Column | Meaning |
| --- | --- |
| `manifest_reference` | `referenced`, `referenced_bundle`, `not_found`, or `not_checked`. |
| `manifest_match` | The matched hash or asset path string, when one was found. |

Output file:

| File | Purpose |
| --- | --- |
| `manifest_refs.csv` | Extracted static strings from local manifest/catalog-like files, including hash-like tokens and asset paths. |

Important boundary: this is static evidence, not a runtime truth oracle. `not_found` means the local manifest scan did not find a matching hash/name/path. It does not prove the asset is never used at runtime, because a game can load by code, remote catalog, generated address, binary-only metadata, or a manifest format this simple scanner cannot fully decode.

## Common Options

| Option | Description |
| --- | --- |
| `--game-root` | Game root containing `XzyLauncher_Data`. Scans both `XzyLauncher_Data/yoo` and `XzyLauncher_Data/StreamingAssets/yoo` when present. |
| `--yoo-root` | Direct path to one YooAssets root. Overrides `--game-root`, so it scans only that one root. |
| `--source-layout` | Source layout to scan with `--game-root`: `all`, `hot`, or `streaming`. Default is `all`. |
| `--out` | Output directory. Defaults to `xzy_assets_out`. |
| `--packages` | Comma-separated package names, for example `Icon,Main,Spine`. Empty means all packages. |
| `--categories` | Comma-separated output categories to export, for example `ui,bgm,models,effects`. Empty means all categories. Valid categories: `ui`, `bgm`, `audio`, `models`, `effects`, `animation`, `prefabs`, `text`, `textures`, `materials`, `raw`, `other`. |
| `--types` | Comma-separated Unity object type names to export, for example `Texture2D,Sprite,AudioClip`. Empty means all types. |
| `--limit` | Maximum bundle count. Defaults to `30`; `0` means all bundles. |
| `--execute` | Actually write files. Without this flag the command is a dry-run. |
| `--no-export` | Classify/decrypt bundles but skip UnityPy object export. |
| `--copy-rawfiles` | Copy local `.rawfile` payloads under `assets/raw/<layout>/<package>/...` and add rows to `assets.csv`. These files are not parsed as Unity bundles. |
| `--keep-bundles` | Save decrypted UnityFS bundles under `decrypted_bundles/`. |
| `--workers` | Number of worker processes for bundle classification/export. Default is `1` for serial mode. Recommended first value for full export: `4`. |
| `--progress-every` | Refresh progress after every N processed bundles. Defaults to `25`; use `1` for the most visible progress and `0` to disable progress output. |
| `--progress-style` | Progress style: `bar`, `lines`, or `none`. `bar` uses Rich when installed and falls back to plain text otherwise. |
| `--no-manifest-check` | Skip static manifest/catalog reference scanning. |
| `--list-packages` | Print the package report and exit without processing bundles. |
| `--fail-on-error` | Return exit code `2` when bundle-level errors are found. Useful for batch scripts or CI. |
| `--ui-packages` | Packages whose `Texture2D` and `Sprite` objects go under `assets/ui`. Default: `Icon,Background,Main,Spine`. |
| `--model-packages` | Packages grouped under `assets/models`. Default: `CharacterMesh,Art3D`. |
| `--effects-packages` | Packages grouped under `assets/effects`. Default includes `BattlePacket`. |
| `--animation-packages` | Packages grouped under `assets/animation` for non-image objects. Default includes `Spine`, `AnimationPacket`, `CharacterTimeline`, `CharacterController`, and `CharacterPerformance`. |

`--packages` decides which YooAssets package folders are scanned. `--categories` decides which classified output groups are written. `--types` is a lower-level Unity object type filter.

## Unity 2022.3 Prefab Reconstruction

The Python extractor does not write Unity native `.prefab` bytes. It writes:

- object-level JSON under `assets/prefabs/...`
- bundle-level `prefab_graph.json`

Use a Unity 2022.3 LTS Editor project to consume those files and rebuild actual prefab assets with `PrefabUtility.SaveAsPrefabAsset`. This is the recommended test baseline for the reconstruction step because the project structure, API set, and serialization behavior are stable enough for repeated smoke tests.

## Packet Raw Containers

Some packages, especially `Assembly`, `BattlePacket`, `Packet`, and `AnimationPacket`, contain non-UnityFS raw packet containers. Export those containers first:

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Assembly,BattlePacket,Packet,AnimationPacket ^
  --categories raw ^
  --no-export ^
  --copy-rawfiles ^
  --out "E:\XZYTool\bin_probe\raw_packet_full" ^
  --limit 0 ^
  --execute ^
  --workers 1 ^
  --progress-style lines ^
  --progress-every 20
```

Then extract packet entries:

```bash
uv run python tools\probe_packets.py ^
  --input "E:\XZYTool\bin_probe\raw_packet_full" ^
  --out "E:\XZYTool\bin_probe\packet_extract_full_decoded" ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --extract ^
  --key-text "GameConfig._EncryptKey text here" ^
  --sample-entries 3
```

The packet tool writes `summary.json`, `packets.csv`, `packet_entries.csv`, previews, and extracted files such as `.json`, `.dll`, `.cpmv`, and `.bin`.

When using `tools/run_full_pipeline.py` or `run_all_windows.bat`, `--key-text` and `--key-hex` are optional. If neither is provided, the pipeline scans `XzyLauncher_Data/resources.assets` near `_GameConfig`, passes the discovered `_EncryptKey` to `probe_packets.py`, and records `packet_key_source` in `pipeline_summary.json`. Direct `probe_packets.py` runs still need the key to be provided explicitly.

Do not commit real keys, game files, or exported assets. Use `--strict-decode` only for algorithm validation; for full extraction, omit it so decoded but unclassified binary payloads are written as `.bin`.

### Packet table `.bin` files

Many `.bin` files inside `Packet/GameTables.p` and `Packet/UiTables.p` are columnar table files, not failed decryptions. Probe them after `probe_packets.py` has written `extracted/`:

```bash
uv run python tools\probe_table_bins.py ^
  --input "E:\XZYTool\bin_probe\packet_extract_full_decoded\extracted" ^
  --out "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --sample-rows 3 ^
  --export-json ^
  --dump-cs "C:\Users\desal\Downloads\Il2CppDumper-win-v6.7.46\dump.cs" ^
  --game-root "E:\XZY\shengtianpc\10046\game"
```

Output files:

| File | Purpose |
| --- | --- |
| `summary.json` | Counts of inspected `.bin` files, parsed tables, non-table files, dump schema matches, and manifest matches. |
| `table_bins.csv` | One row per `.bin`, including packet asset name, table candidate, match status, field names, and parser error if any. |
| `previews/` | Metadata plus the first sampled rows for each parsed table. |
| `tables_json/` | Full table rows when `--export-json` is enabled. |

`--dump-cs` is optional but recommended. It parses `Table*.tData` and `UiTable*.tData` structs from Il2CppDumper output and uses their field order to rename columns. `--game-root` or repeated `--packet-manifest` inputs let the tool map packet bundle hashes back to `GameTables`, `UiTables`, `Languages`, and similar manifest asset names.

Match statuses:

| Status | Meaning |
| --- | --- |
| `unique_signature` | The table column type signature matches exactly one `tData` struct. Field names are applied. |
| `package_preferred` | Multiple structs share the same type signature, but `GameTables`/`UiTables` package context selects one. Field names are applied. |
| `ambiguous_signature` | Multiple structs still match. The tool lists candidates and keeps generated `col_XX_type` names. |
| `package_ambiguous` | Package context narrowed the candidates but did not make them unique. |
| `no_match` | Parsed as a table, but no matching `tData` signature was found in the supplied `dump.cs`. |
| `not_checked` | No `dump.cs` was supplied. |

### Searchable table text

After `probe_table_bins.py` writes `tables_json/`, use `extract_table_texts.py` to build a practical text index. This is the easiest way to inspect activity UI copy, item names, banner text, descriptions, and other table-driven strings.

Activity/UI focused extraction:

```bash
uv run python tools\extract_table_texts.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --out "E:\XZYTool\table_texts_activity" ^
  --table-regex "UiTableActivity|UiTableJumpAdBanner|UiTableGlobal" ^
  --field-regex "Comment|Description|Title|Name|Text|StringValue|Choice" ^
  --export-json
```

Full CJK text index:

```bash
uv run python tools\extract_table_texts.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --out "E:\XZYTool\table_texts_all" ^
  --only-cjk
```

Output files:

| File | Purpose |
| --- | --- |
| `table_texts.csv` | Searchable UTF-8 with BOM CSV. Open with Excel, VS Code, or another UTF-8 aware editor. |
| `table_texts.json` | Optional JSON rows when `--export-json` is set. |
| `summary.json` | Counts by table and text kind. |

Useful filters:

| Option | Meaning |
| --- | --- |
| `--table-regex` | Limits rows by table name, packet asset name/path, or relative `.bin` path. |
| `--field-regex` | Limits string fields by field name. Supplying it also includes matching non-CJK strings. |
| `--keyword` | Keeps only strings containing a keyword. Can be repeated. |
| `--only-cjk` | Keeps only strings containing CJK characters. |
| `--all-strings` | Includes all non-empty strings except dates unless `--include-dates` is set. |
| `--max-records` | Caps records for quick testing. `0` means no limit. |

If Chinese appears garbled in PowerShell, verify the CSV/JSON with a UTF-8 aware editor before changing the decoder. The table parser stores strings as UTF-8; console code pages can display correct text incorrectly.

### Remaining non-table `.bin` files

After the table probe, inspect the `.bin` files that are not parsed as tables:

```bash
uv run python tools\probe_binary_bins.py ^
  --input "E:\XZYTool\bin_probe\packet_extract_full_decoded\extracted" ^
  --out "E:\XZYTool\bin_probe\binary_probe_named" ^
  --table-report "E:\XZYTool\bin_probe\table_bin_probe_named\table_bins.csv" ^
  --game-root "E:\XZY\shengtianpc\10046\game"
```

The binary probe writes `binary_bins.csv`, `summary.json`, and per-file previews. Current categories include `animation_like`, `animation_state_skeleton`, `unity_yaml_meta`, `collision_like`, `string_list`, `binary_with_strings`, `tiny_placeholder`, and `binary_unknown`.

`animation_state_skeleton` means the file is a small no-string `AnimationPacket` payload with count-like records, known role action IDs such as `S1`/`S2`/`EX`, or all-zero placeholder bytes. It is evidence of animation state data, not a missed image/audio/model export.

### Gameplay and battle tables

After `probe_table_bins.py` has generated `tables_json/`, export the gameplay-facing tables into a smaller directory that is easier to inspect:

```bash
uv run python tools\export_gameplay_tables.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --out "E:\XZYTool\gameplay_tables" ^
  --include-ui-skill
```

This writes standalone JSON and CSV files. The CSV files use UTF-8 with BOM and can be opened directly in Excel or WPS. Arrays are preserved as compact JSON strings inside CSV cells so each original row remains one spreadsheet row.

Useful output examples:

| File | Typical content |
| --- | --- |
| `gameplay_tables/skills/cooldown/csv/TableAmmoIndex.csv` | Ammo count, cooldown, recovery, initial amount, and replenish flags. |
| `gameplay_tables/skills/damage/csv/TableDamageIndex.csv` | Damage ratio, EX gain, stun/down, damage reduction, rune/achievement hooks. |
| `gameplay_tables/skills/bullet/csv/TableBulletIndex.csv` | Bullet model, performance id, animator controller, pre-create count. |
| `gameplay_tables/skills/buff/csv/TableBuffIndex.csv` | Buff type, append type, duration, float/string parameters, VFX, removal flags. |
| `gameplay_tables/skills/talent/csv/TableTalentIndex.csv` | Talent ids, types, numeric values, and string parameters. |
| `gameplay_tables/characters/stats/csv/TableCharacterParameter.csv` | HP, power, boost, lock distance, movement ratios, hit clear times. |
| `gameplay_tables/characters/base/csv/TableCharacterIndex.csv` | Character config, model, performance, icon, and build asset flag. |
| `gameplay_tables/tables.csv` | Index of every exported gameplay table and its source Packet path. |

`tools/run_full_pipeline.py` and `run_all_windows.bat` run this step automatically and also request `.xlsx` workbooks. For manual runs, JSON and CSV are always written; add `--xlsx` when you also want `gameplay_tables.xlsx`.

### Classified named tables

`gameplay_tables/` focuses on battle and character gameplay. The remaining named tables still contain valuable configuration, especially items, activity missions, shops, matchmaking, global settings, and visual references. Export them with:

```bash
uv run python tools\export_classified_tables.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --table-texts "E:\XZYTool\table_texts_all" ^
  --out "E:\XZYTool\classified_tables"
```

Add `--xlsx` if you want `classified_tables.xlsx`. `openpyxl` is part of the uv-managed project dependencies.

Main output buckets include `items_economy`, `activity_mission`, `shop_monetization`, `match_rank_battle_ui`, `navigation_tutorial`, `system_global`, `visual_refs`, `equipment_loadout`, `social_communication`, `settings_region`, and `review`.

### Business index

After the raw extractor, packet probes, and text indexing are in place, use `organize_exports.py` to build a practical browsing layer:

```bash
uv run python tools\organize_exports.py ^
  --input "E:\XZYTool" ^
  --out "E:\XZYTool\organized" ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_v6_named" ^
  --table-texts "E:\XZYTool\table_texts_all"
```

The organizer does not move the original evidence. It writes CSV/JSON indexes under:

```text
organized/
  _index/
  characters/
  skills/
  ui/
  audio/
  visual/
  packets/
  review/
```

Use `characters/` for base stats and role data, `skills/` for cooldown and skill tables, `ui/` for activity and banner text, and `review/` for unresolved or ambiguous rows.
It also writes `organized/README.md` as a short first-open navigation page.

### Example buckets

- `characters/character_basic.csv`
- `characters/character_stats.csv`
- `characters/character_voice.csv`
- `skills/skill_cooldowns.csv`
- `skills/skill_groups.csv`
- `skills/skill_damage.csv`
- `ui/activity_texts.csv`
- `ui/banner_texts.csv`
- `audio/bgm.csv`
- `visual/models.csv`
- `packets/tables.csv`
- `review/no_match_tables.csv`

## Background Package Note

Some hot-update packages contain only `ManifestFiles/*.bytes` and `.hash` files, but no `BundleFiles/**/__data`. In that case the manifest may list paths such as `Assets/GameData/UiBackgrounds/*.png`, but the actual hot-update bundles are not present in that root. The extractor cannot recreate images from a manifest alone.

For this project, many built-in bundles live under `XzyLauncher_Data/StreamingAssets/yoo/<Package>/*.bundle`; use `--game-root` instead of pointing `--yoo-root` only at `XzyLauncher_Data/yoo` if you want a full local scan.

Use `--list-packages` to confirm whether a package has real bundle files.

## Troubleshooting

### `UnityPy is not installed`

Sync dependencies and run through uv:

```bash
uv sync
uv run python -c "import UnityPy; print(UnityPy.__file__)"
```

### `Imported a UnityPy module without load/Environment`

`uv run python` imported the wrong `UnityPy` module. Check:

- `uv run python -c "import UnityPy; print(UnityPy.__file__)"`
- whether another `UnityPy.py` file exists in the repository or current shell path
- whether the command was run outside the repository root

### No images exported from a package

Check:

- `package_report.csv`: package has `bundle_count > 0`
- `bundles.csv`: mode is `plain_unityfs` or `tail16_xor_unityfs`
- `assets.csv`: object statuses and categories
- `errors.json`: bundle-level errors

## Tests

The unit tests use synthetic temporary bundles and do not require real game files:

```bash
uv run python -m unittest discover -s tests
```

By default, test temporary data is created under `E:\XZYTool\_extractor_test_tmp`. Override it with `XZY_EXTRACTOR_TEST_TMP` when needed.

Syntax check:

```bash
uv run python -m py_compile xzy_yooasset_extractor.py
```

## Legal and Ethical Use

This repository is licensed for the extractor source code only. It does not grant rights to any third-party game content.

Do not use this project to upload, redistribute, sell, or publish assets you do not own or do not have permission to use. Follow the applicable game EULA, platform rules, and local law.

## License

Code in this repository is released under the MIT License. See [LICENSE](LICENSE).
