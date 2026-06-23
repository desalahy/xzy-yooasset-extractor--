# XZY YooAsset Extractor 中文说明

这是一个本地研究和学习用的 YooAssets/Unity 资源包检查工具。它可以扫描 `XzyLauncher_Data/yoo` 目录，识别普通 UnityFS 包，也能处理一种“文件末尾 16 字节作为 XOR key”的资源包格式。

仓库只应该包含脚本、文档和测试。

## 安装

推荐 Python 3.10 或更新版本。

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

如果依赖已经安装在别的目录，可以传入：

```bash
python xzy_yooasset_extractor.py --deps-dir C:\path\to\site-packages ...
```

或设置环境变量：

```bash
set UNITYPY_DEPS_DIR=C:\path\to\site-packages
```

## 快速使用

列出本地 YooAssets 包：

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --list-packages
```

先做 dry-run，不写文件：

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --limit 2
```

导出 UI 相关图片：

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon,Main,Spine ^
  --out "E:\XZY\UI" ^
  --limit 0 ^
  --execute ^
  --progress-every 20
```

只分类和解密，不用 UnityPy 导出对象：

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --no-export ^
  --execute
```

保存解密后的 UnityFS bundle：

```bash
python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --keep-bundles ^
  --execute
```

## 输出文件

输出目录中会生成：

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
    animation/
    prefabs/
    text/
    textures/
```

重点看这几个文件：

- `package_report.csv`: 每个包是否存在 `BundleFiles`、bundle 数量、manifest 数量。
- `bundles.csv`: 每个 bundle 的识别模式、原始头部、解密后头部。
- `assets.csv`: Unity 对象级索引，包括类型、`path_id`、资源名、导出路径、状态。
- `errors.json`: bundle 级错误。
- `summary.json`: 本次运行摘要。

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

如果 `plain` 开头变成 `UnityFS`，就说明这个包是 `tail16_xor_unityfs`。

## Background 包说明

有些本地安装里 `Background` 包只有：

```text
ManifestFiles/*.bytes
*.hash
```

但没有：

```text
BundleFiles/**/__data
```

这种情况下，清单里能看到 `Assets/GameData/UiBackgrounds/*.png`，但实际图片包不在本地，脚本不能只凭清单还原图片。需要先让客户端把对应 bundle 下载到本地。

## 测试

测试不依赖真实游戏文件。运行：

```bash
python -m unittest discover -s tests
```

语法检查：

```bash
python -m py_compile xzy_yooasset_extractor.py
```

## 开源和版权边界

本仓库当前代码使用 MIT License。MIT 只覆盖本仓库里的提取器源码和文档，不覆盖任何第三方游戏资源。

请不要上传、传播、售卖或公开展示你没有授权的图片、音频、模型、bundle、metadata 或其他受版权保护内容。
