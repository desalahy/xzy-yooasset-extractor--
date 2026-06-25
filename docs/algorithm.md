# 解密和导出思路

本文记录脚本采用的处理流程，方便后续维护或学习。

## 1. YooAssets 目录结构

本工具现在支持两个本地 YooAssets 资源来源。

热更目录：

```text
XzyLauncher_Data/
  yoo/
    Icon/
      BundleFiles/
        xx/
          <bundle_hash>/
            __data
      ManifestFiles/
    Main/
    Spine/
```

内置 StreamingAssets 目录：

```text
XzyLauncher_Data/
  StreamingAssets/
    yoo/
      Icon/
        <bundle_hash>.bundle
        Icon.bytes
        Icon.hash
      Bgm/
      CharacterMesh/
```

`--game-root` 会默认同时扫描这两个目录。`--source-layout hot` 只扫热更目录，`--source-layout streaming` 只扫 StreamingAssets，默认 `all` 两个都扫。`--yoo-root` 只代表一个已经定位好的 YooAssets 根目录，所以它不会自动帮你补另一个来源。

脚本内部会先把实际可处理的文件统一成 `BundleCandidate`：

| 来源 | 实际 bundle 文件 | hash 名称来源 |
| --- | --- | --- |
| `hot_update` | `BundleFiles/**/__data` | `__data` 的父目录名 |
| `streaming_assets` | `<Package>/**/*.bundle` | `.bundle` 文件名去掉扩展名 |

只有 manifest/catalog 文件的包只能生成包报告和引用线索，不能凭空导出资源实体。

另外，StreamingAssets 里可能有 `.rawfile`。它们不进入 Unity bundle 解密流程；开启 `--copy-rawfiles` 时，脚本会把它们原样复制到 `assets/raw/<layout>/<package>/...` 并写入 `assets.csv`，状态为 `copied_rawfile`。

## 2. 识别 Unity bundle

Unity bundle 常见文件头：

```text
UnityFS
UnityRaw
UnityWeb
```

如果 bundle 原始头部就是这些 magic，脚本标记为：

```text
plain_unityfs
```

## 3. 尾部 16 字节 XOR 解密

当前样本里，部分 bundle 的最后 16 字节是 key。真正的数据区是前面的全部字节。

伪代码：

```python
key = blob[-16:]
encrypted = blob[:-16]
plain = bytes(encrypted[i] ^ key[i % 16] for i in range(len(encrypted)))
```

如果 `plain` 的开头变成 `UnityFS/UnityRaw/UnityWeb`，脚本标记为：

```text
tail16_xor_unityfs
```

这对应 YooAssets 自定义 `BundleStream` 常见写法：读取文件末尾 16 字节为 `m_Key`，然后在 `Read()` 时按当前位置对读取缓冲区做循环 XOR。

## 4. UnityPy 导出

解密得到 UnityFS 后，脚本把 bytes 交给 UnityPy：

```python
env = UnityPy.load(bundle_bytes)
for obj in env.objects:
    data = obj.read()
```

常见导出规则：

| Unity 类型 | 导出 |
| --- | --- |
| `Texture2D` | PNG |
| `Sprite` | PNG |
| `AudioClip` | sample 音频 |
| `TextAsset` / `MonoScript` / `Shader` | 文本或二进制 |
| 其他对象 | 记录到 `assets.csv`，状态为 `listed_only` |

## 5. 分类规则

默认把这些包里的图片归入 UI：

```text
Icon, Background, Main, Spine
```

因此输出类似：

```text
assets/ui/hot_update/Icon/<bundle_hash>/*.png
assets/ui/streaming_assets/Icon/<bundle_hash>/*.png
assets/ui/streaming_assets/Spine/<bundle_hash>/*.png
```

中间的 `hot_update` / `streaming_assets` 是来源标记，用来避免两个来源里同名 package 或同名 hash 互相覆盖。可以用 `--ui-packages` 改 UI 分类规则。

## 6. 索引文件

`bundles.csv` 记录 bundle 层：

- 来源 layout：`hot_update` 或 `streaming_assets`
- 包名
- bundle hash
- 识别模式
- 原始路径
- 原始头部
- 解密后头部

`assets.csv` 记录对象层：

- 来源 layout
- 包名
- bundle hash
- Unity 对象类型
- `path_id`
- 资源名
- 输出路径
- 导出状态
- manifest 静态引用状态

如果开启 `--copy-rawfiles`，`.rawfile` 也会进入 `assets.csv`，但它的 `type` 是 `RawFile`，`bundle_mode` 是 `rawfile`。这表示“原始载荷已复制”，不表示 UnityPy 已经解析出内部对象。

`manifest_refs.csv` 记录从本地 manifest/catalog 类文件里提取出的线索：

- hash-like token
- `Assets/...` 资源路径
- 其他包含路径分隔符的可读字符串

扫描规则：

| 来源 | 静态引用文件 |
| --- | --- |
| `hot_update` | `ManifestFiles/**/*` |
| `streaming_assets` | `.bytes`、`.json`、`.hash`、`.version` |

`manifest_reference` 的含义：

| 值 | 含义 |
| --- | --- |
| `referenced` | 当前 bundle hash 或 asset 名称/路径在本地 manifest 静态扫描中被匹配到。 |
| `referenced_bundle` | asset 名称未直接匹配，但所在 bundle hash 被本地 manifest 引用。 |
| `not_found` | 本地 manifest 静态扫描没有找到对应线索。 |
| `not_checked` | 使用了 `--no-manifest-check`，没有扫描 manifest。 |

这个检查只能回答“本地 manifest 文本/可读字符串中有没有线索”，不能证明运行时一定使用或一定不使用。运行时还可能通过远程 catalog、代码路径、生成地址、二进制表或其他加载逻辑引用资源。

`errors.json` 只记录 bundle 级异常。对象级失败会写进 `assets.csv` 的 `status`，例如 `sprite_failed:...`。

## 7. 进度显示

主循环会先收集本次要处理的 `BundleCandidate` 列表，所以可以得到总数。这个列表同时包含热更 `__data` 和 StreamingAssets `.bundle`。进度条显示：

- 已处理 bundle 数 / 总数
- 百分比
- `assets.csv` 当前行数
- 错误数
- 已耗时
- 预计剩余时间

`--progress-style bar` 适合人工观察；`--progress-style lines` 适合保存日志；`--progress-every 0` 可以关闭进度。

## 8. 局限

- 不能凭 YooAssets manifest 还原缺失的 bundle。
- UnityPy 无法解析的 Unity 版本或自定义对象只能列索引。
- `tail16_xor_non_unity` 可能仍是有效资源，但不是 UnityFS，需要针对具体格式继续分析。
- `manifest_reference=not_found` 不等于运行时一定不用，只代表当前静态扫描没有找到证据。
