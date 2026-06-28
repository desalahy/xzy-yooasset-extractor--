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

## 8. Packet/bin raw 容器

`Assembly`、`BattlePacket`、`Packet`、`AnimationPacket` 中存在一类非 UnityFS 容器。主脚本只负责把它们识别为 `non_unity_raw` 并原样导出；进一步拆内部条目由 `tools/probe_packets.py` 完成。

外层 packet 格式：

```text
byte    encrypted_flag      0 = 明文条目，1 = AES 加密条目
int32   entry_count

if encrypted_flag == 1:
  repeat entry_count:
    uint32 file_id
    int32  origin_length
    int32  stored_length
    bytes  payload[stored_length]

if encrypted_flag == 0:
  repeat entry_count:
    uint32 file_id
    int32  length
    bytes  payload[length]
```

加密条目使用 AES-CBC。key 来自游戏配置里的 `_GameConfig._EncryptKey`，实战样本中它是 32 个可见字符，直接按 UTF-8 字节作为 AES-256 key 使用，不做 base64 解码。

IV 来自逻辑 packet 名：

```python
def iv_from_name(name: str) -> bytes:
    raw = name.encode("utf-8")
    return raw[:16].ljust(16, b"\x00")
```

逻辑名不是 hash 文件名，而是 manifest 里的资源名或资源路径 basename。例如：

| manifest 资源路径 | IV 名 |
| --- | --- |
| `Assets/GameData/BattlePackets/GameBehavior18.p` | `GameBehavior.p` |
| `Assets/GameData/BattlePackets/GameAccessories.p` | `GameAccessories.p` |
| `Assets/GameData/Packets/UiTables.p` | `UiTables.p` |
| `Assets/GameData/Packets/GameTables.p` | `GameTables.p` |
| `Assets/GameData/AssemblyPackets/Assembly_Windows_3.1.0.p` | `Assembly_Windows_3.1.0.p` |

`BattlePacket` 的分片名可能带数字，例如 `GameBehavior18.p`。代码会在 stem 不含版本点号时去掉末尾数字，得到主包名 `GameBehavior.p`。`Assembly_Windows_3.1.0.p` 这种带版本点号的名字不会去数字。

manifest 解析目前覆盖两种 `RawFileBuildPipeline` 记录格式：

| 模式 | 常见包 | 特征 |
| --- | --- | --- |
| `fixed` | `BattlePacket`、`Assembly` | asset 记录后有固定长度字段，bundle 记录尾部也可固定跳过。 |
| `builtin` | `Packet` | asset 和 bundle 记录中包含 `Builtin` 字符串。 |

`xzy_yooasset_core.manifest.parse_rawfile_manifest()` 会把 bundle hash 映射到 `asset_name`、`asset_path`、`bundle_name`。`tools/probe_packets.py` 再用这个映射生成 IV 候选并解密 payload。

导出后缀规则：

| 输出后缀 | 判断方式 |
| --- | --- |
| `.json` | 解密后以 `{` 或 `[` 开头。 |
| `.dll` | 通过 PE 头校验。 |
| `.cpmv` | 以 `CPMV` magic 开头。 |
| `.bin` | 已解密或明文提取，但当前还没有更细的格式识别器。 |
| `.encrypted` | 没有 key/IV，AES 失败，或显式启用 `--strict-decode` 且解密结果评分太低。 |

全量拆内容时通常不要加 `--strict-decode`。低评分并不一定代表解密失败，也可能只是自定义二进制表。要做算法验证时才建议开启 strict。

## 9. Packet 表格 `.bin` 二级格式

`probe_packets.py` 导出的 `.bin` 里，有一部分不是加密残留，而是 `Packet/GameTables.p`、`Packet/UiTables.p` 内部的表格数据。`tools/probe_table_bins.py` 负责解析这一层。

表格文件头：

```text
int32 row_count
int32 column_count
repeat column_count:
  byte type_name_length
  bytes type_name_utf8[type_name_length]
```

后续数据是列式存储，不是行式存储：

```text
for column in columns:
  for row in rows:
    value encoded by column type
```

也就是说，文件不是这样存：

```text
row0_col0, row0_col1, row1_col0, row1_col1
```

而是这样存：

```text
col0_row0, col0_row1, col1_row0, col1_row1
```

当前已验证的基础类型：

| 类型 | 编码 |
| --- | --- |
| `byte` | 1 字节无符号整数。 |
| `ushort` | little-endian uint16。 |
| `uint` | little-endian uint32。 |
| `int` | little-endian int32。 |
| `long` | little-endian int64。 |
| `ulong` | little-endian uint64。 |
| `float` | little-endian IEEE754 float32。 |
| `double` | little-endian IEEE754 float64。 |
| `bool` | 1 字节，非 0 为 true。 |
| `string` | 1 字节长度 + UTF-8 字节。 |
| `DateTime` | 当前样本中也是 1 字节长度 + UTF-8 日期字符串。 |
| `enum:*` | little-endian uint32，枚举名只用于字段类型匹配。 |
| `T[]` | int32 数组长度 + 重复写入 T 类型元素。 |

字段名不是 `.bin` 里直接给出的。恢复字段名靠 `dump.cs`：

1. 从 Il2CppDumper 的 `dump.cs` 中扫描 `public struct TableName.tData`。
2. 按字段顺序提取 C# 类型和字段名。
3. 把 C# 类型转换成表格类型签名，例如 `uint|string|bool`。
4. 把 `.bin` 文件头里的列类型也拼成同样的签名。
5. 签名唯一匹配时，把 `tData` 字段名应用到 JSON 行数据。

示例：

```text
.bin 类型签名:
uint|uint|enum:eEquipmentSlot|string|string|string|enum:eEquipmentAnimationType|string

dump.cs 匹配:
TableAccessoryIndex.tData

字段名:
Id|UserId|Slot|Config|Model|AnimationFolder|OverrideAnimationType|Name
```

如果多个 `tData` 结构体有完全一样的字段类型，工具不会硬猜。它会结合 Packet manifest 里的逻辑包名做一次保守筛选：

| 包名 | 偏好 |
| --- | --- |
| `GameTables` | 优先非 `UiTable*`。 |
| `UiTables` | 优先 `UiTable*`。 |

筛选后唯一就是 `package_preferred`；仍不唯一就是 `package_ambiguous` 或 `ambiguous_signature`。这种保守策略比“看起来像哪个表就命名哪个表”更适合教程和开源工具，因为它会明确告诉使用者哪些地方仍需要人工或更深的代码证据。

## 10. 表格文本索引

`probe_table_bins.py` 已经把表格 `.bin` 还原成了 `tables_json/`，但直接阅读几百个 JSON 不适合定位活动 UI 文案、道具名、描述、按钮文本或提示文本。`tools/extract_table_texts.py` 是建立在表格 JSON 之上的二次索引工具，它不重新解密，也不重新解析 `.bin`。

处理流程：

1. 读取 `table_bins.csv`，建立 `.bin` 相对路径到表名、匹配状态、packet 资源名和资源路径的映射。
2. 遍历 `tables_json/**/*.json`。
3. 对每一行表数据递归展开字符串字段，数组和嵌套对象会保留类似 `Choice[0]`、`Config.Title` 的字段路径。
4. 根据 `--table-regex`、`--field-regex`、`--keyword`、`--only-cjk` 等参数过滤。
5. 给文本打上轻量标签，例如 `comment`、`description`、`title`、`name`、`url`、`resource_ref`、`cjk_text`。
6. 写出 `table_texts.csv`、可选 `table_texts.json` 和 `summary.json`。

默认策略偏向“文案检索”：

| 规则 | 说明 |
| --- | --- |
| 默认字段 | 字段名命中 `name/title/text/textid/desc/comment/content/message/dialog/choice/label/language/string`。 |
| CJK 文本 | 只要字符串包含中日韩字符，即使字段名不明显，也会保留。 |
| URL | URL 会保留，方便审计活动入口、公告、跳转配置。 |
| 日期 | 类似 `2023-07-17 05:00:00` 的日期默认跳过，避免刷屏；需要时加 `--include-dates`。 |
| CSV 编码 | `table_texts.csv` 使用 UTF-8 with BOM，优先照顾 Excel/WPS 打开。 |

这一步解决的是“拆出来以后怎么查文字”的问题，不解决“字段名是否 100% 唯一”的问题。`ambiguous_signature` 或 `<unknown>` 表仍会导出文本，但要把它们当成“内容可读、表名未完全确认”的证据。

如果 PowerShell 显示中文乱码，先用 UTF-8 编辑器或 Python 验证文件内容。当前样本里，表格字符串本身是 UTF-8；终端显示乱码不等于 `.bin` 解码错误。

## 11. 非表格 `.bin` 指纹分类

`probe_table_bins.py` 只能解析表格。剩下的 `.bin` 不一定是加密失败，也不一定都是可还原成图片、音频、模型的资源。`tools/probe_binary_bins.py` 做的是轻量级指纹分类。

处理顺序是保守的：

1. 先识别 Unity YAML 文本。
2. 再看头部可读字符串是否命中动画、碰撞体等关键词。
3. 再尝试把整个文件当字符串列表读。
4. 最后抽取普通 ASCII 片段。
5. 仍没有证据时才落到 `binary_unknown`。

`AnimationPacket` 有一类特殊文件：没有任何可读动画名，但字节结构非常像动画状态骨架。工具会把它们归为 `animation_state_skeleton`。判断条件包括：

```text
路径包含 AnimationPacket
文件较小
没有 ASCII 字符串
非零字节比例低
并且满足以下任一项：
  - 全零小文件
  - 第 1 个字节像 count，后面长度能被 count 整除
  - 前 4 字节像 int32 count，后面长度能被 count 整除
  - 文件头附近出现已知动作枚举值，例如 S1=500、S2=505、EX=520
```

实战样本里最典型的是 144 字节文件：

```text
0b                                      # 11 条记录
00 00 01 00 00 00 00 00 00 01 00 02 02
...
```

`0x0b = 11`，剩余 `143` 字节正好等于 `11 * 13`。文件里没有 `skill_`、`combat_loop` 这类 clip 名称，也没有图片、音频、模型 magic。它不是“没解开的大资源”，而是“无字符串的小型动画状态记录”。

另一个样本以动作 ID 开头：

```text
0d f4 01 04 00 ...
```

这里 `f4 01` 是 little-endian 的 `500`，对应 `eRoleActType.S1`；后面的 `04` 对应动画状态类型里的 `Motion`。这类证据只能说明它属于动画状态数据，不能直接还原成可播放动画片段。

当前验证过的非表格 `.bin` 分类结果：

| 分类 | 数量 | 说明 |
| --- | ---: | --- |
| `animation_like` | 264 | 带动画名字符串的 AnimationPacket 二进制。 |
| `animation_state_skeleton` | 19 | 无字符串的动画状态骨架或占位。 |
| `unity_yaml_meta` | 88 | Unity YAML 元信息。 |
| `collision_like` | 38 | 碰撞/边界/trigger 类二进制。 |
| `tiny_placeholder` | 9 | 小占位文件。 |
| `binary_with_strings` | 8 | 可抽出字符串但暂未细分。 |
| `string_list` | 4 | 可按字符串列表读取。 |
| `binary_unknown` | 0 | 当前样本里没有剩余未知项。 |

这一步的价值是审计，而不是导出更多美术资源。它告诉你：剩余 `.bin` 中哪些已经可以解释，哪些真的值得继续投入格式逆向。

## 12. 局限

- 不能凭 YooAssets manifest 还原缺失的 bundle。
- UnityPy 无法解析的 Unity 版本或自定义对象只能列索引。
- `non_unity_raw` 可能仍是有效资源，但不是 UnityFS，需要继续用 packet/bin 探测或针对具体格式写二级解析器。
- `manifest_reference=not_found` 不等于运行时一定不用，只代表当前静态扫描没有找到证据。
