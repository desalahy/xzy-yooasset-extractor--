# XZY YooAsset Extractor 中文说明

这是一个本地研究和学习用的 YooAssets/Unity 资源解包工具。它会扫描 `XzyLauncher_Data/yoo` 目录，识别普通 UnityFS bundle，也能处理一种“文件末尾 16 字节作为 XOR key”的资源加密格式。

## 安装

推荐 Python 3.10 或更新版本。

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## 先看有哪些包

先列出本地 YooAssets 包，确认哪些包有 `BundleFiles`。

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --list-packages
```

如果你已经定位到了 `yoo` 目录，也可以直接用 `--yoo-root`：

```bash
python xzy_yooasset_extractor.py ^
  --yoo-root "E:\XZY\shengtianpc\10046\game\XzyLauncher_Data\yoo" ^
  --list-packages
```

## 先小范围测试

不加 `--execute` 时只做 dry-run，不会写入导出文件。适合先确认脚本能跑通。

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --limit 2
```

`--limit 2` 表示最多处理 2 个 bundle。默认不传 `--limit` 时只处理 30 个 bundle；全量处理要写 `--limit 0`。

## 全量导出所有包

不传 `--packages` 就会扫描所有包；`--limit 0` 表示不限制 bundle 数量。

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --out "E:\XZY\AllAssets" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

这会尽量导出 UnityPy 能读取的资源，包括 UI 图片、BGM、音效、语音、贴图、模型相关对象、动画相关对象、特效相关对象、文本和材质等。

`--progress-every 20` 只控制进度日志：每处理 20 个 bundle 打印一次当前进度。它不会限制导出数量，也不会影响导出内容。设置为 `0` 可以关闭进度输出。

注意：全量导出可能很大，也可能运行很久。建议先用 `--list-packages` 看包数量，再用少量包测试，确认没问题后再全量导出。

## 全量分类但不导出资源

如果只想知道每个 bundle 的识别模式，不想导出图片、音频、模型，可以加 `--no-export`。

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --out "E:\XZY\BundleIndex" ^
  --limit 0 ^
  --no-export ^
  --execute ^
  --progress-every 50
```

这会生成 `package_report.csv`、`bundles.csv`、`errors.json`、`summary.json`，适合先做资源包盘点和解密模式确认。

## 只导出 UI 图片

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon,Main,Spine ^
  --categories ui ^
  --types Texture2D,Sprite ^
  --out "E:\XZY\UI" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

说明：

- `Icon` 通常包含 UI 图标、活动图、道具图。
- `Main` 里常见 UI 图、界面 prefab 相关对象。
- `Spine` 可能包含 UI Spine 贴图，也可能包含动画数据。
- `--categories ui` 表示只写出分类为 UI 的对象。
- `--types Texture2D,Sprite` 表示只写出 Unity 图片对象。

## 只导出 BGM

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Bgm ^
  --categories bgm ^
  --types AudioClip ^
  --out "E:\XZY\BGM" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

`Bgm` 包会被归到 `assets/bgm/`。`--types AudioClip` 可以避免把同一个包里的非音频对象也写出来。

## 只导出音效和语音

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Se,Voice ^
  --categories audio ^
  --types AudioClip ^
  --out "E:\XZY\Audio" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

`Se` 通常是音效，`Voice` 通常是语音。它们会归到 `assets/audio/`。

## 只导出模型相关资源

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages CharacterMesh,Art3D ^
  --categories models,materials,textures ^
  --out "E:\XZY\Models" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

说明：

- `CharacterMesh` 和 `Art3D` 是本地包名里最明显的模型相关包。
- `models` 主要对应 Unity 的 `Mesh` 对象。
- `materials`、`textures` 是模型经常需要的材质和贴图，不一起导出会导致模型内容不完整。
- 这个脚本偏向“提取对象和索引”，不是完整的 Unity 场景/Prefab 还原器。

## 只导出特效相关资源

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages BattlePacket,AnimationPacket,CharacterPerformance ^
  --categories effects,animation,materials,textures,prefabs ^
  --out "E:\XZY\Effects" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

说明：

- 特效资源常常不是单独一个文件，而是 prefab、动画、材质、贴图、粒子系统等组合。
- `effects` 会收集明显的粒子/特效对象，或者名称里带 `effect`、`vfx`、`fx`、`particle` 的对象。
- `animation`、`materials`、`textures`、`prefabs` 一起导出，后续排查特效时更有用。
- 如果你发现某个特效包没有被归到 `effects`，可以用 `--effects-packages 包名1,包名2` 补充规则。

## 只导出动画相关资源

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Spine,AnimationPacket,CharacterTimeline,CharacterController,CharacterPerformance ^
  --categories animation ^
  --out "E:\XZY\Animation" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

`animation` 通常包含 `AnimationClip`、`AnimatorController`、`Avatar` 等对象，也会包含部分 Spine 文本/二进制数据。

## 只解密和分类，不用 UnityPy 导对象

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --no-export ^
  --execute
```

这个命令会生成索引文件，但不会拆 Unity 对象。适合确认加密和 bundle 类型。

## 保存解密后的 UnityFS bundle

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --keep-bundles ^
  --execute
```

全量保存解密后的 bundle 也可以，但会占用更多磁盘：

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --out "E:\XZY\AllBundles" ^
  --limit 0 ^
  --keep-bundles ^
  --execute
```

## 输出文件

输出目录里会生成：

```text
out/
  package_report.csv
  bundles.csv
  assets.csv
  errors.json
  summary.json
  assets/
    ui/
    audio/
    bgm/
    models/
    effects/
    animation/
    prefabs/
    text/
    textures/
    materials/
    raw/
    other/
```

重点看这几个文件：

- `package_report.csv`: 每个包是否存在 `BundleFiles`、bundle 数量、manifest 数量。
- `bundles.csv`: 每个 bundle 的识别模式、原始头部、解密后头部。
- `assets.csv`: Unity 对象清单，包含类型、`path_id`、资源名、分类、导出路径、状态。
- `errors.json`: bundle 级错误。
- `summary.json`: 本次运行摘要。

如果全量导出后想知道某个文件在哪里，先查 `assets.csv` 的 `output` 列，再看同一行的 `package`、`bundle_hash`、`type`、`path_id`。

如果使用了 `--categories` 或 `--types`，被过滤掉的对象仍会出现在 `assets.csv`，状态会是 `skipped_category` 或 `skipped_type`。

## Windows 批处理示例

`examples/` 目录里有几份可以双击运行的 `.bat` 示例。运行前先打开文件，把 `GAME_ROOT` 和 `OUT_DIR` 改成你自己的路径。

| 文件 | 用途 |
| --- | --- |
| `examples/extract_all_windows.bat` | 全量导出所有本地包。 |
| `examples/extract_ui_windows.bat` | 只导出 UI 图片。 |
| `examples/extract_bgm_windows.bat` | 只导出 BGM。 |
| `examples/extract_models_windows.bat` | 只导出模型、材质、贴图相关对象。 |
| `examples/extract_effects_windows.bat` | 只导出特效、动画、材质、贴图、prefab 相关对象。 |

## 参数说明

| 参数 | 作用 |
| --- | --- |
| `--game-root "E:\...\game"` | 游戏根目录。脚本会自动找 `XzyLauncher_Data/yoo`。 |
| `--yoo-root "E:\...\XzyLauncher_Data\yoo"` | 直接指定 YooAssets 根目录。传了它就会覆盖 `--game-root`。 |
| `--out "E:\XZY\UI"` | 输出目录。不传时默认是当前目录下的 `xzy_assets_out`。 |
| `--packages Icon,Main,Spine` | 只扫描指定包。不传就是扫描所有包。 |
| `--categories ui,bgm,models,effects` | 只导出指定分类。不传就是所有分类都导出。可用分类包括 `ui`、`bgm`、`audio`、`models`、`effects`、`animation`、`prefabs`、`text`、`textures`、`materials`、`raw`、`other`。 |
| `--types Texture2D,Sprite,AudioClip` | 只导出指定 Unity 对象类型。不传就是所有类型都导出。 |
| `--limit 2` | 最多处理 2 个 bundle，适合测试。 |
| `--limit 0` | 不限制 bundle 数量，适合全量导出。 |
| `--execute` | 真的写出文件。不加这个参数就是 dry-run。 |
| `--no-export` | 只识别和解密 bundle，不让 UnityPy 导出内部对象。 |
| `--keep-bundles` | 保存解密后的 UnityFS bundle。 |
| `--deps-dir C:\path\to\site-packages` | 指定 UnityPy 等依赖所在目录。 |
| `--progress-every 20` | 每处理 20 个 bundle 打印一次进度。只影响日志，不影响导出内容。 |
| `--progress-every 0` | 关闭进度输出。 |
| `--list-packages` | 只列出包信息，然后退出。 |
| `--fail-on-error` | 如果出现 bundle 级错误，进程返回码为 `2`，适合批处理或 CI 检查。 |
| `--ui-packages Icon,Background,Main,Spine` | 自定义哪些包的图片默认归到 `assets/ui`。 |
| `--model-packages CharacterMesh,Art3D` | 自定义哪些包默认归到 `assets/models`。 |
| `--effects-packages BattlePacket,Effect` | 自定义哪些包默认归到 `assets/effects`。 |
| `--animation-packages Spine,AnimationPacket` | 自定义哪些包的非图片对象默认归到 `assets/animation`。 |

`--packages`、`--categories`、`--types` 的区别很重要：

- `--packages` 是第一层过滤：决定扫描哪些 YooAssets 包。
- `--categories` 是第二层过滤：决定写出哪些资源分类，比如 `ui`、`bgm`、`models`。
- `--types` 是更底层的 Unity 类型过滤，比如只要 `AudioClip` 或只要 `Texture2D,Sprite`。

## 解密规则

脚本先判断文件是否直接以 Unity magic 开头：

```text
UnityFS
UnityRaw
UnityWeb
```

如果不是，就尝试尾部 16 字节 XOR：

```python
key = blob[-16:]
encrypted = blob[:-16]
plain = bytes(encrypted[i] ^ key[i % 16] for i in range(len(encrypted)))
```

如果 `plain` 开头变成 `UnityFS`，说明它是 `tail16_xor_unityfs`。

## Background 包说明

有些本地安装里的 `Background` 包只有：

```text
ManifestFiles/*.bytes
*.hash
```

但没有：

```text
BundleFiles/**/__data
```

这种情况下，清单里可能看到 `Assets/GameData/UiBackgrounds/*.png`，但实际图片不在本地。脚本不能只凭清单还原图片，需要客户端把对应 bundle 下载到本地。

## 测试

测试不需要真实游戏文件：

```bash
python -m unittest discover -s tests
```

语法检查：

```bash
python -m py_compile xzy_yooasset_extractor.py
```

## 开源和版权边界

本仓库使用 MIT License。MIT 只覆盖本仓库里的提取脚本、测试和文档，不覆盖任何第三方游戏资源。

请不要上传、发布或公开展示没有授权的图片、音频、模型、bundle、metadata 或其他可能受版权保护的内容。
