# XZY YooAsset Extractor

Chinese documentation is available in [docs/zh-CN.md](docs/zh-CN.md).

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

- Scans `XzyLauncher_Data/yoo` package directories.
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
- Writes reproducible indexes:
  - `package_report.csv`
  - `bundles.csv`
  - `assets.csv`
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


## Quick Start

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
  --out "E:\XZY\UI" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
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

## Output Layout

```text
out/
  package_report.csv
  bundles.csv
  assets.csv
  errors.json
  summary.json
  assets/
    ui/
      Icon/<bundle_hash>/*.png
      Main/<bundle_hash>/*.png
      Spine/<bundle_hash>/*.png
    audio/
    bgm/
    models/
    animation/
    prefabs/
    text/
    textures/
```

`assets.csv` is the main lookup table. Each row includes package name, bundle hash, bundle mode, Unity object type, `path_id`, original asset name, output category, output path, and export status.

## Common Options

| Option | Description |
| --- | --- |
| `--game-root` | Game root containing `XzyLauncher_Data/yoo`. |
| `--yoo-root` | Direct YooAssets root path. Overrides `--game-root`. |
| `--packages` | Comma-separated package names, for example `Icon,Main,Spine`. |
| `--limit` | Maximum bundle count. `0` means all bundles. |
| `--execute` | Actually write files. Without this flag the command is a dry-run. |
| `--no-export` | Classify/decrypt bundles but skip UnityPy object export. |
| `--keep-bundles` | Save decrypted UnityFS bundles under `decrypted_bundles/`. |
| `--progress-every` | Print progress after every N bundles. |
| `--ui-packages` | Packages whose `Texture2D` and `Sprite` objects go under `assets/ui`. |
| `--deps-dir` | Optional dependency directory containing UnityPy. |

## Background Package Note

Some installations contain a `Background` package with only `ManifestFiles/*.bytes` and `.hash` files, but no `BundleFiles/**/__data`. In that case the manifest may list paths such as `Assets/GameData/UiBackgrounds/*.png`, but the actual bundles are not present locally. The extractor cannot recreate images from a manifest alone.

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

Syntax check:

```bash
python -m py_compile xzy_yooasset_extractor.py
```

## Legal and Ethical Use

This repository is licensed for the extractor source code only. It does not grant rights to any third-party game content.

Do not use this project to upload, redistribute, sell, or publish assets you do not own or do not have permission to use. Follow the applicable game EULA, platform rules, and local law.

## License

Code in this repository is released under the MIT License. See [LICENSE](LICENSE).
