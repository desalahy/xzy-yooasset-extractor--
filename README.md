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
- UnityPy
- Pillow

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

If dependencies are already installed in a separate directory, pass that directory explicitly:

```bash
python xzy_yooasset_extractor.py --deps-dir C:\path\to\site-packages ...
```

or set:

```bash
set UNITYPY_DEPS_DIR=C:\path\to\site-packages
```

## Project Layout

| Path | Purpose |
| --- | --- |
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
| `tests/` | Unit tests with synthetic bundles; no real game files are required. |

## Quick Start

On Windows, the simplest entry point is:

```bat
run_wizard_windows.bat
```

It opens folder pickers for the game root and output folder, then asks which export mode to run and how many worker processes to use. With `--game-root`, the extractor scans both `XzyLauncher_Data/yoo` and `XzyLauncher_Data/StreamingAssets/yoo` when those directories exist.

List available YooAssets packages:

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --list-packages
```

Dry-run two Icon bundles:

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --limit 2
```

Export UI-related packages:

```bash
python xzy_yooasset_extractor.py ^
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
python xzy_yooasset_extractor.py ^
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
python xzy_yooasset_extractor.py ^
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
python xzy_yooasset_extractor.py ^
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
python xzy_yooasset_extractor.py ^
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
python xzy_yooasset_extractor.py ^
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
python xzy_yooasset_extractor.py ^
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
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --no-export ^
  --execute
```

Save decrypted UnityFS bundles as well:

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --keep-bundles ^
  --execute
```

## Windows Batch Examples

The recommended Windows entry point is `run_wizard_windows.bat`, which lets you choose folders interactively.

The `examples/` directory also contains double-clickable batch files. They now `cd` back to the project root before running, so they can find `xzy_yooasset_extractor.py` even when launched from inside `examples/`. Edit `GAME_ROOT`, `OUT_DIR`, and optionally `WORKERS` inside each file before running:

| File | Purpose |
| --- | --- |
| `run_wizard_windows.bat` | Interactive folder and mode selector. |
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
```

`assets.csv` is the main lookup table. Each row includes source layout, package name, bundle hash, bundle mode, Unity object type, `path_id`, original asset name, output category, output path, export status, and local manifest reference evidence.

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
| `--deps-dir` | Optional dependency directory containing UnityPy. |
| `--workers` | Number of worker processes for bundle classification/export. Default is `1` for serial mode. Recommended first value for full export: `4`. |
| `--progress-every` | Refresh progress after every N processed bundles. Defaults to `25`; use `1` for the most visible progress and `0` to disable progress output. |
| `--progress-style` | Progress style: `bar`, `lines`, or `none`. Default is `bar`. |
| `--no-manifest-check` | Skip static manifest/catalog reference scanning. |
| `--list-packages` | Print the package report and exit without processing bundles. |
| `--fail-on-error` | Return exit code `2` when bundle-level errors are found. Useful for batch scripts or CI. |
| `--ui-packages` | Packages whose `Texture2D` and `Sprite` objects go under `assets/ui`. Default: `Icon,Background,Main,Spine`. |
| `--model-packages` | Packages grouped under `assets/models`. Default: `CharacterMesh,Art3D`. |
| `--effects-packages` | Packages grouped under `assets/effects`. Default includes `BattlePacket`. |
| `--animation-packages` | Packages grouped under `assets/animation` for non-image objects. Default includes `Spine`, `AnimationPacket`, `CharacterTimeline`, `CharacterController`, and `CharacterPerformance`. |

`--packages` decides which YooAssets package folders are scanned. `--categories` decides which classified output groups are written. `--types` is a lower-level Unity object type filter.

## Background Package Note

Some hot-update packages contain only `ManifestFiles/*.bytes` and `.hash` files, but no `BundleFiles/**/__data`. In that case the manifest may list paths such as `Assets/GameData/UiBackgrounds/*.png`, but the actual hot-update bundles are not present in that root. The extractor cannot recreate images from a manifest alone.

For this project, many built-in bundles live under `XzyLauncher_Data/StreamingAssets/yoo/<Package>/*.bundle`; use `--game-root` instead of pointing `--yoo-root` only at `XzyLauncher_Data/yoo` if you want a full local scan.

Use `--list-packages` to confirm whether a package has real bundle files.

## Troubleshooting

### `UnityPy is not installed`

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

### `Imported a UnityPy module without load/Environment`

Python imported the wrong `UnityPy` module. Check:

- the active virtual environment
- `PYTHONPATH`
- `UNITYPY_DEPS_DIR`
- the value passed to `--deps-dir`

### No images exported from a package

Check:

- `package_report.csv`: package has `bundle_count > 0`
- `bundles.csv`: mode is `plain_unityfs` or `tail16_xor_unityfs`
- `assets.csv`: object statuses and categories
- `errors.json`: bundle-level errors

## Tests

The unit tests use synthetic temporary bundles and do not require real game files:

```bash
python -m unittest discover -s tests
```

By default, test temporary data is created under `E:\XZYTool\_extractor_test_tmp`. Override it with `XZY_EXTRACTOR_TEST_TMP` when needed.

Syntax check:

```bash
python -m py_compile xzy_yooasset_extractor.py
```

## Legal and Ethical Use

This repository is licensed for the extractor source code only. It does not grant rights to any third-party game content.

Do not use this project to upload, redistribute, sell, or publish assets you do not own or do not have permission to use. Follow the applicable game EULA, platform rules, and local law.

## License

Code in this repository is released under the MIT License. See [LICENSE](LICENSE).
