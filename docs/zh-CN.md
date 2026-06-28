# XZY YooAsset Extractor 中文说明

这是一个本地研究和学习用的 YooAssets/Unity 资源解包工具。使用 `--game-root` 时，它会同时扫描两个本地 YooAssets 来源：

- 热更目录：`XzyLauncher_Data/yoo/<Package>/BundleFiles/**/__data`
- 内置资源目录：`XzyLauncher_Data/StreamingAssets/yoo/<Package>/*.bundle`

它能识别普通 UnityFS bundle，也能处理一种“文件末尾 16 字节作为 XOR key”的资源加密格式。

## 安装

推荐 Python 3.10 或更新版本。项目依赖统一交给 `uv` 管理，不要手工创建额外的依赖目录。

```bash
uv sync
```

如果你的机器上 uv 读取全局 managed Python 目录时报权限错误，可以先指定已有 Python 解释器：

```bat
set UV_PYTHON=D:\Python\python.exe
uv sync
```

## 项目代码结构

| 路径 | 作用 |
| --- | --- |
| `agent.md` | 给下一个 AI 接手项目用的交接文档。 |
| `xzy_yooasset_extractor.py` | 兼容入口文件。继续用 `uv run python xzy_yooasset_extractor.py ...` 运行即可。 |
| `xzy_yooasset_core/cli.py` | 命令行参数解析和主流程编排。 |
| `xzy_yooasset_core/discovery.py` | 查找 YooAssets 根目录、package、`.bundle`、`__data`、`.rawfile`。 |
| `xzy_yooasset_core/bundle.py` | bundle 头部探测、尾部 16 字节 XOR 解密、bundle 模式分类。 |
| `xzy_yooasset_core/exporter.py` | UnityPy 对象导出、输出路径分配、rawfile 原样复制。 |
| `xzy_yooasset_core/manifest.py` | manifest/catalog 静态字符串扫描和引用匹配。 |
| `xzy_yooasset_core/models.py` | 扫描、导出和 CLI 共用的数据结构。 |
| `xzy_yooasset_core/constants.py` | CSV 字段、分类名、静态后缀列表。 |
| `xzy_yooasset_core/progress.py` | 进度条和逐行进度输出。 |
| `xzy_yooasset_core/utils.py` | 路径、CSV、字符串等小工具函数。 |
| `tools/probe_packets.py` | 侦查和拆解 Packet/BattlePacket/Assembly 这类非 UnityFS raw 容器。 |
| `tools/probe_table_bins.py` | 解析 Packet 里导出的表格 `.bin`，输出表格预览和可选 JSON。 |
| `tools/extract_table_texts.py` | 从表格 JSON 里抽取可搜索的中文文案、活动 UI 文本和描述字段。 |
| `tools/export_gameplay_tables.py` | 把已解析出的角色、战斗、技能、弹药、伤害、子弹、Buff、天赋等表，单独导出成 JSON 和 Excel 可直接打开的 CSV。 |
| `tools/export_classified_tables.py` | 把剩余已命名表继续分成道具经济、活动任务、商城充值、匹配排位、系统全局、视觉引用等目录。 |
| `tools/probe_binary_bins.py` | 对剩余非表格 `.bin` 做轻量级指纹分类。 |
| `tools/probe_string_bins.py` | 实验性字符串列表探测器，用于继续侦查特殊二进制字符串。 |
| `docs/project-history.md` | 项目历史、关键决策、踩坑记录和不要丢失的约束。 |
| `docs/project-status-and-roadmap.md` | 给人看的项目现状、能力边界和后续开发路线。 |
| `tests/` | 单元测试，只用合成 bundle，不需要真实游戏文件。 |

## Windows 最简单入口

双击项目根目录下的：

```bat
run_wizard_windows.bat
```

它会弹窗让你选择游戏根目录和输出目录，然后让你选择导出模式：UI、BGM、音效/语音、模型、特效、全量或只做 bundle 索引，最后询问 worker 进程数。默认 worker 数是 4。只要选择的是游戏根目录，脚本默认会同时扫描 `XzyLauncher_Data/yoo` 和 `XzyLauncher_Data/StreamingAssets/yoo`。

## 先看有哪些包

先列出本地 YooAssets 包，确认哪些包有热更 `BundleFiles`、哪些包有 StreamingAssets `.bundle`。

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --list-packages
```

如果你已经定位到了某一个 `yoo` 目录，也可以直接用 `--yoo-root`：

```bash
uv run python xzy_yooasset_extractor.py ^
  --yoo-root "E:\XZY\shengtianpc\10046\game\XzyLauncher_Data\yoo" ^
  --list-packages
```

注意：`--yoo-root` 只扫描你指定的这一个根目录。想完整扫描本地资源，推荐传 `--game-root "...\game"`，不要只传 `XzyLauncher_Data\yoo`。

## 先小范围测试

不加 `--execute` 时只做 dry-run，不会写入导出文件。适合先确认脚本能跑通。

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --limit 2
```

`--limit 2` 表示最多处理 2 个 bundle。默认不传 `--limit` 时只处理 30 个 bundle；全量处理要写 `--limit 0`。

## 全量导出所有包

不传 `--packages` 就会扫描所有包；`--limit 0` 表示不限制 bundle 数量。默认 `--source-layout all`，也就是热更目录和 StreamingAssets 目录都扫。

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

这会尽量导出 UnityPy 能读取的资源，包括 UI 图片、BGM、音效、语音、贴图、模型相关对象、动画相关对象、特效相关对象、文本和材质等。

`--copy-rawfiles` 会额外复制本地 `.rawfile` payload 到 `assets/raw/<layout>/<package>/...`，并写入 `assets.csv`。这类文件不当作 UnityFS bundle 解析，只做原样归档。

如果你之前只得到了约 2GB 输出，常见原因是只扫描了 `XzyLauncher_Data/yoo` 热更目录，漏掉了更大的 `XzyLauncher_Data/StreamingAssets/yoo`。用上面的 `--game-root` 全量命令会把两个来源都纳入扫描。

`--workers 4` 表示用 4 个工作进程并行处理 bundle 的识别、解密和 UnityPy 导出。建议先从 `4` 开始；如果 CPU 和磁盘还有余量，再试 `6` 或 `8`。不要盲目开太高，图片/音频写盘和 UnityPy 解析会抢磁盘，进程太多可能反而变慢。

`--progress-style bar` 会显示可视化进度条，包含总数、百分比、已耗时、预计剩余时间、资产行数和错误数。`--progress-every 1` 表示每处理 1 个 bundle 刷新一次。它不会限制导出数量，也不会影响导出内容。设置 `--progress-style lines` 可以改成逐行日志，设置 `--progress-every 0` 可以关闭进度输出。

注意：全量导出可能很大，也可能运行很久。建议先用 `--list-packages` 看包数量，再用少量包测试，确认没问题后再全量导出。

## 全量分类但不导出资源

如果只想知道每个 bundle 的识别模式，不想导出图片、音频、模型，可以加 `--no-export`。

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

这会生成 `package_report.csv`、`bundles.csv`、`errors.json`、`summary.json`，适合先做资源包盘点和解密模式确认。

你也可以只盘点某一个来源：

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --source-layout streaming ^
  --out "E:\XZY\BundleIndexStreaming" ^
  --limit 0 ^
  --no-export ^
  --execute ^
  --progress-style lines
```

`--source-layout hot` 只扫 `XzyLauncher_Data/yoo`，`--source-layout streaming` 只扫 `XzyLauncher_Data/StreamingAssets/yoo`，默认 `all` 两个都扫。

## 只导出 UI 图片

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon,Main,Spine ^
  --categories ui ^
  --types Texture2D,Sprite ^
  --out "E:\XZY\UI" ^
  --limit 0 ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar
```

说明：

- `Icon` 通常包含 UI 图标、活动图、道具图。
- `Main` 里常见 UI 图、界面 prefab 相关对象。
- `Spine` 可能包含 UI Spine 贴图，也可能包含动画数据。
- `--categories ui` 表示只写出分类为 UI 的对象。
- `--types Texture2D,Sprite` 表示只写出 Unity 图片对象。

## 只导出 BGM

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

`Bgm` 包会被归到 `assets/bgm/`。`--types AudioClip` 可以避免把同一个包里的非音频对象也写出来。

## 只导出音效和语音

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

`Se` 通常是音效，`Voice` 通常是语音。它们会归到 `assets/audio/`。

## 只导出模型相关资源

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

说明：

- `CharacterMesh` 和 `Art3D` 是本地包名里最明显的模型相关包。
- `models` 主要对应 Unity 的 `Mesh` 对象。
- `materials`、`textures` 是模型经常需要的材质和贴图，不一起导出会导致模型内容不完整。
- 这个脚本偏向“提取对象和索引”，不是完整的 Unity 场景/Prefab 还原器。

## 只导出特效相关资源

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

说明：

- 特效资源常常不是单独一个文件，而是 prefab、动画、材质、贴图、粒子系统等组合。
- `effects` 会收集明显的粒子/特效对象，或者名称里带 `effect`、`vfx`、`fx`、`particle` 的对象。
- `animation`、`materials`、`textures`、`prefabs` 一起导出，后续排查特效时更有用。
- `AnimationPacket` 这类包里可能有 `.rawfile`，加 `raw` 分类和 `--copy-rawfiles` 后会原样复制出来。
- 如果你发现某个特效包没有被归到 `effects`，可以用 `--effects-packages 包名1,包名2` 补充规则。

## 只导出动画相关资源

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Spine,AnimationPacket,CharacterTimeline,CharacterController,CharacterPerformance ^
  --categories animation ^
  --out "E:\XZY\Animation" ^
  --limit 0 ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar
```

`animation` 通常包含 `AnimationClip`、`AnimatorController`、`Avatar` 等对象，也会包含部分 Spine 文本/二进制数据。

## 只解密和分类，不用 UnityPy 导对象

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --no-export ^
  --execute
```

这个命令会生成索引文件，但不会拆 Unity 对象。适合确认加密和 bundle 类型。

## 保存解密后的 UnityFS bundle

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --packages Icon ^
  --keep-bundles ^
  --execute
```

全量保存解密后的 bundle 也可以，但会占用更多磁盘：

```bash
uv run python xzy_yooasset_extractor.py ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --out "E:\XZY\AllBundles" ^
  --limit 0 ^
  --keep-bundles ^
  --execute
```

## Packet/bin 容器解包

`Assembly`、`BattlePacket`、`Packet`、`AnimationPacket` 这类包里有一些内容不是 UnityFS bundle。主脚本会先把它们归类为 `non_unity_raw`，然后可以用 `tools/probe_packets.py` 继续拆内部条目。

第一步，先把 Packet 类 raw 容器完整导出到一个单独目录：

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

第二步，用 packet 探测工具解析容器并导出内部条目：

```bash
uv run python tools\probe_packets.py ^
  --input "E:\XZYTool\bin_probe\raw_packet_full" ^
  --out "E:\XZYTool\bin_probe\packet_extract_full_decoded" ^
  --game-root "E:\XZY\shengtianpc\10046\game" ^
  --extract ^
  --key-text "这里填 GameConfig._EncryptKey 的 32 字符字符串" ^
  --sample-entries 3
```

`--key-text` 不是 base64 解码后的值，而是 `_GameConfig._EncryptKey` 里那段 32 个字符本身。不要把真实 key、真实游戏资源或导出内容提交到 GitHub。

如果使用 `tools/run_full_pipeline.py` 或 `run_all_windows.bat`，可以不传 `--key-text` / `--key-hex`。完整流水线会从 `XzyLauncher_Data/resources.assets` 的 `_GameConfig` 附近自动读取 `_EncryptKey`，传给 `probe_packets.py`，并在 `pipeline_summary.json` 里记录 `packet_key_source`。单独运行 `tools/probe_packets.py` 时仍然需要手动传 key。

输出内容：

| 文件 | 作用 |
| --- | --- |
| `summary.json` | 本次 packet 扫描总数、有效容器数、加密容器数、条目数。 |
| `packets.csv` | 每个外层 packet/bin/rawfile 容器的解析结果。 |
| `packet_entries.csv` | 每个内部条目的长度、解密状态、输出路径。 |
| `previews/` | 每个容器的少量条目预览，便于快速判断格式。 |
| `extracted/` | 真正导出的内部内容，常见后缀是 `.json`、`.dll`、`.cpmv`、`.bin`。 |

我在当前样本上验证过的结果是：347 个 packet 容器全部可解析，65 个带加密标记，合计 19824 个内部条目；不启用 `--strict-decode` 时输出为 18852 个 `.json`、906 个 `.bin`、44 个 `.cpmv`、22 个 `.dll`，没有剩余 `.encrypted`。

`--strict-decode` 只建议用于算法验证。它会把“已经 AES 解密成功但暂时无法识别格式”的低评分二进制保守地留下为 `.encrypted`。如果目标是全量拆出内容，通常不要加 `--strict-decode`，让这些内容落为 `.bin`，后续再继续研究二级格式。

第三步，继续解析 `Packet/GameTables.p` 和 `Packet/UiTables.p` 里的表格 `.bin`：

```bash
uv run python tools\probe_table_bins.py ^
  --input "E:\XZYTool\bin_probe\packet_extract_full_decoded\extracted" ^
  --out "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --sample-rows 3 ^
  --export-json ^
  --dump-cs "C:\Users\desal\Downloads\Il2CppDumper-win-v6.7.46\dump.cs" ^
  --game-root "E:\XZY\shengtianpc\10046\game"
```

这个工具解决的是“`.bin` 里面还有一层表格格式”的问题。它会读取行数、列数、列类型，然后按列把数据还原成 JSON。

输出内容：

| 文件 | 作用 |
| --- | --- |
| `summary.json` | 统计扫描了多少 `.bin`、多少能解析成表、多少不是表、多少匹配到 `dump.cs` 字段结构。 |
| `table_bins.csv` | 每个 `.bin` 的包逻辑名、表名候选、匹配状态、字段名和错误信息。 |
| `previews/` | 每张表的元信息和前几行样本。 |
| `tables_json/` | 加了 `--export-json` 后写出的完整表数据。 |

`--dump-cs` 用来读取 Il2CppDumper 生成的 `Table*.tData` / `UiTable*.tData` 结构体。工具会用结构体字段顺序把 `col_00_uint` 这类机械列名还原成 `Id`、`Name`、`Config` 等字段名。

`--game-root` 会自动读取本地 Packet manifest，把 hash 目录识别为 `GameTables`、`UiTables`、`Languages`、`Tutorial` 等逻辑包名。如果不想传游戏目录，也可以用 `--packet-manifest` 手动传 `.bytes` manifest；热更和 StreamingAssets 各传一次即可。

`table_bins.csv` 里的 `match_status` 需要这样看：

| 状态 | 含义 |
| --- | --- |
| `unique_signature` | 列类型签名只匹配到一个 `tData`，字段名可信度最高。 |
| `package_preferred` | 多个 `tData` 类型一样，但根据 `GameTables` / `UiTables` 包名能选出一个，字段名会应用。 |
| `ambiguous_signature` | 多个结构体字段类型完全一样，不能安全确定表名，只列出候选。 |
| `package_ambiguous` | 包名能缩小候选范围，但仍然不唯一。 |
| `no_match` | `.bin` 能解析成表，但当前 `dump.cs` 没有找到同样的字段类型签名。 |
| `not_checked` | 没有传 `--dump-cs`，所以没有做字段名恢复。 |

我在当前样本上验证过的表格结果是：906 个 `.bin` 中有 476 个是表格；其中 300 个唯一匹配字段结构，12 个靠包名偏好匹配，129 个保持签名歧义，6 个是包名缩小范围后仍不唯一，29 个没有在当前 `dump.cs` 里找到对应签名。保守留下歧义是故意的，避免把同字段结构的不同业务表误命名。

第三步之后，如果你关心游戏文本、活动 UI 文案、活动任务描述、道具名和表字段，不要直接在几百个 JSON 里人工翻。先把 `tables_json/` 生成一个可搜索文本索引。

只提取活动/UI 相关文案：

```bash
uv run python tools\extract_table_texts.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --out "E:\XZYTool\table_texts_activity" ^
  --table-regex "UiTableActivity|UiTableJumpAdBanner|UiTableGlobal" ^
  --field-regex "Comment|Description|Title|Name|Text|StringValue|Choice" ^
  --export-json
```

全量提取所有包含中文的表格字符串：

```bash
uv run python tools\extract_table_texts.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --out "E:\XZYTool\table_texts_all" ^
  --only-cjk
```

输出文件：

| 文件 | 作用 |
| --- | --- |
| `table_texts.csv` | 可搜索 CSV，使用 UTF-8 with BOM，适合 Excel、VS Code、WPS 打开。 |
| `table_texts.json` | 加 `--export-json` 时额外输出，适合后续脚本继续处理。 |
| `summary.json` | 按表名和文本类型统计本次抽取结果。 |

常用参数：

| 参数 | 含义 |
| --- | --- |
| `--table-regex` | 按表名、packet 资源名、资源路径或 `.bin` 相对路径过滤。 |
| `--field-regex` | 按字段名过滤，例如只看 `Comment|Description|Title|Name`。 |
| `--keyword` | 只保留包含某个关键词的文本，可以重复传多次。 |
| `--only-cjk` | 只保留包含中文/中日韩字符的字符串。 |
| `--all-strings` | 导出所有非空字符串；默认仍会跳过日期，除非加 `--include-dates`。 |
| `--max-records` | 快速测试时限制输出行数；`0` 表示不限制。 |

我在当前样本上实测过两份索引：活动/UI 过滤版输出 3542 条文本，覆盖 48 张表；全量中文索引输出 81069 条文本，覆盖 273 张表。这里面能看到 `UiTableActivityMission`、`UiTableActivityChatEvent`、`UiTableJumpAdBanner`、`UiTableItem`、`UiTableRoleArchives` 等内容。

如果你在 PowerShell 里看到中文乱码，不要立刻判断为解码失败。当前表格字符串是按 UTF-8 读出的，乱码通常是终端代码页显示问题。优先用 Excel、VS Code 或 Python 以 UTF-8 打开 `table_texts.csv` / `table_texts.json` 验证。

### 战斗、角色、技能配置导出

`probe_table_bins.py` 产出的 `tables_json/` 是完整表集合，但目录按 Packet 原始 hash 排列，不适合直接找“伤害表”“弹药表”“角色参数表”。如果你关心战斗数值、机体基础配置、技能冷却、子弹、Buff、天赋、核心、配件等配置，用下面这个二次导出器：

```bash
uv run python tools\export_gameplay_tables.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --out "E:\XZYTool\gameplay_tables" ^
  --include-ui-skill
```

它会输出 JSON 和 CSV 两套文件：

| 路径 | 内容 |
| --- | --- |
| `gameplay_tables/tables.csv` | 本次导出的表清单、分类、源 Packet 路径、行数和输出文件路径。 |
| `gameplay_tables/skills/cooldown/csv/TableAmmoIndex.csv` | 弹药数量、冷却、回复时间、初始数量、是否 EX 补充等。 |
| `gameplay_tables/skills/damage/csv/TableDamageIndex.csv` | 伤害倍率、EX 获取、硬直、倒地、减伤、符文/成就钩子等。 |
| `gameplay_tables/skills/bullet/csv/TableBulletIndex.csv` | 子弹模型、表现名、AnimatorController、预创建数量等。 |
| `gameplay_tables/skills/buff/csv/TableBuffIndex.csv` | Buff 类型、叠加方式、持续时间、数值参数、字符串参数、特效和移除条件。 |
| `gameplay_tables/skills/talent/csv/TableTalentIndex.csv` | 天赋 ID、类型、数值参数和字符串参数。 |
| `gameplay_tables/characters/stats/csv/TableCharacterParameter.csv` | HP、Power、Boost、锁定距离、移动倍率、受击清除时间等角色基础参数。 |
| `gameplay_tables/characters/base/csv/TableCharacterIndex.csv` | 角色配置名、模型、Performance、Icon、是否 BuildAsset。 |

CSV 使用 UTF-8 with BOM，Excel / WPS / VS Code 可以直接打开。数组字段会以一小段 JSON 字符串放在单元格里，这样能保持“原始表一行 = CSV 一行”。这一步目前不强依赖 `.xlsx` 写库；如果需要带样式的 xlsx，可以后续从这些 CSV 再生成工作簿。

一键完整流水线和 `run_all_windows.bat` 已经会自动生成 `gameplay_tables/`，手动命令主要用于你已经有 `table_bin_probe_named/`，不想重新拆包时单独补导出。

### 其他有价值表的分类导出

`gameplay_tables/` 只放战斗和角色玩法表。剩余已命名表里仍然有很多有价值配置，例如道具、活动任务、商城、充值、匹配、排位、全局参数、Spine/视觉引用、地区语言等。可以继续导出到 `classified_tables/`：

```bash
uv run python tools\export_classified_tables.py ^
  --table-probe "E:\XZYTool\bin_probe\table_bin_probe_named" ^
  --table-texts "E:\XZYTool\table_texts_all" ^
  --out "E:\XZYTool\classified_tables"
```

如果你需要 `.xlsx` 浏览工作簿，直接加：

```bash
--xlsx
```

`openpyxl` 已经在 `pyproject.toml` 里，由 `uv sync` 安装到项目 `.venv`。

主要分类包括：`items_economy`、`activity_mission`、`shop_monetization`、`match_rank_battle_ui`、`navigation_tutorial`、`system_global`、`visual_refs`、`equipment_loadout`、`social_communication`、`settings_region`、`review`。

第四步，继续侦查剩下那些“不是表格”的 `.bin`：

```bash
uv run python tools\probe_binary_bins.py ^
  --input "E:\XZYTool\bin_probe\packet_extract_full_decoded\extracted" ^
  --out "E:\XZYTool\bin_probe\binary_probe_named" ^
  --table-report "E:\XZYTool\bin_probe\table_bin_probe_named\table_bins.csv" ^
  --game-root "E:\XZY\shengtianpc\10046\game"
```

这个工具不负责把 `.bin` 强行还原成 Unity 资源，它负责回答“剩下的二进制更像什么”。输出内容：

| 文件 | 作用 |
| --- | --- |
| `summary.json` | 统计每种二进制分类各有多少。 |
| `binary_bins.csv` | 每个非表格 `.bin` 的路径、大小、分类、头部字节、可读字符串和 manifest 线索。 |
| `previews/` | 每个文件的少量预览 JSON，适合人工抽查。 |

当前分类含义：

| 分类 | 含义 |
| --- | --- |
| `animation_like` | `AnimationPacket` 里带有 `skill_`、`shoot_`、`combat_loop` 等动画字符串的二进制。 |
| `animation_state_skeleton` | `AnimationPacket` 里没有字符串，但有计数字段、低熵小记录、`S1`/`S2`/`EX` 等动作 ID，或者全零占位。它更像动画状态骨架，不是漏导出的图片、音频或模型。 |
| `unity_yaml_meta` | Unity 文本 YAML 元信息。 |
| `collision_like` | 带碰撞体、边界、trigger 等字符串的二进制。 |
| `string_list` | 可以按字符串列表格式完整读出的文件。 |
| `binary_with_strings` | 不是表格，但能抽出一些可读字符串。 |
| `tiny_placeholder` | 很小的占位文件。 |
| `binary_unknown` | 目前仍没有足够证据分类，需要继续人工分析。 |

我在当前样本上复查过：表格解析后的 430 个非表格 `.bin` 中，264 个是 `animation_like`，19 个是 `animation_state_skeleton`，88 个是 `unity_yaml_meta`，38 个是 `collision_like`，9 个是 `tiny_placeholder`，8 个是 `binary_with_strings`，4 个是 `string_list`，没有剩余 `binary_unknown`。这说明现阶段剩下的 `.bin` 已经能按用途解释，不能再简单理解成“还有大量美术资源没导出”。

当前工具已经能从 YooAsset `RawFileBuildPipeline` manifest 里解析 hash 到逻辑名的映射。例如：

- `Assets/GameData/BattlePackets/GameBehavior18.p` 会推导 IV 名 `GameBehavior.p`。
- `Assets/GameData/Packets/UiTables.p` 会推导 IV 名 `UiTables.p`。

IV 规则是：把逻辑名按 UTF-8 转字节，截断或补零到 16 字节。AES key 来自 `_GameConfig._EncryptKey`，模式是 AES-CBC。

## 输出文件

输出目录里会生成：

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
      hot_update/
      streaming_assets/
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

- `package_report.csv`: 每个包的来源、bundle 数量、热更 `__data` 数量、StreamingAssets `.bundle` 数量、`.rawfile` 数量、manifest/catalog 数量。
- `bundles.csv`: 每个 bundle 的识别模式、原始头部、解密后头部。
- `assets.csv`: Unity 对象清单，包含类型、`path_id`、资源名、分类、导出路径、状态。
- `manifest_refs.csv`: 从本地 manifest/catalog 类文件里静态提取出来的 hash、资源路径和可读字符串。
- `errors.json`: bundle 级错误。
- `summary.json`: 本次运行摘要。

实际导出的文件会多一层来源目录，例如：

```text
assets/ui/hot_update/Icon/<bundle_hash>/*.png
assets/ui/streaming_assets/Icon/<bundle_hash>/*.png
assets/bgm/streaming_assets/Bgm/<bundle_hash>/*.wav
decrypted_bundles/streaming_assets/Icon/<bundle_hash>.bundle
raw/hot_update/Icon/<bundle_hash>.bin
assets/raw/streaming_assets/AnimationPacket/*.rawfile
```

这层 `hot_update` / `streaming_assets` 用来避免两个来源里出现同名 package 或同名 hash 时互相覆盖。

如果全量导出后想知道某个文件在哪里，先查 `assets.csv` 的 `output` 列，再看同一行的 `layout`、`package`、`bundle_hash`、`type`、`path_id`。

如果使用了 `--categories` 或 `--types`，被过滤掉的对象仍会出现在 `assets.csv`，状态会是 `skipped_category` 或 `skipped_type`。

## 如何判断是否被当前项目实际引用

脚本现在会默认扫描本地 manifest/catalog 类文件，并在 `bundles.csv` 和 `assets.csv` 里写入：

| 字段 | 含义 |
| --- | --- |
| `manifest_reference` | `referenced`、`referenced_bundle`、`not_found` 或 `not_checked`。 |
| `manifest_match` | 匹配到的 hash 或资源路径。 |

热更目录会扫描 `ManifestFiles/**/*`；StreamingAssets 目录会扫描 `.bytes`、`.json`、`.hash`、`.version` 文件。

这些字段只能说明“本地 manifest 静态扫描是否找到线索”，不能 100% 证明运行时是否使用。原因是游戏可能通过代码、远程 catalog、生成地址、二进制表或当前扫描器没完全解析的格式加载资源。

实用判断方式：

- `referenced`: 本地 manifest 里找到了明确 hash、资源名或路径线索，优先认为和项目有关。
- `referenced_bundle`: asset 名称没直接匹配，但它所在 bundle hash 被 manifest 引用，说明这一包更可能有用。
- `not_found`: 本地 manifest 静态扫描没找到，不等于运行时一定没用。
- `not_checked`: 使用了 `--no-manifest-check`，没有做检查。

## Windows 批处理示例

推荐先用项目根目录的 `run_wizard_windows.bat`，它可以弹窗选择游戏目录和输出目录。模式 1-7 只做导出，模式 8 才会跑完整流水线，模式 9 会复用已有 `raw/` 继续后续阶段。

`examples/` 目录里还有几份可以双击运行的 `.bat` 示例。它们会自动回到项目根目录再运行，所以能找到外层的 `xzy_yooasset_extractor.py`。运行前先打开文件，把 `GAME_ROOT`、`OUT_DIR` 和可选的 `WORKERS` 改成你自己的设置。

| 文件 | 用途 |
| --- | --- |
| `run_wizard_windows.bat` | 交互选择游戏目录、输出目录和导出模式。 |
| `examples/extract_all_windows.bat` | 全量导出所有本地包。 |
| `examples/extract_ui_windows.bat` | 只导出 UI 图片。 |
| `examples/extract_bgm_windows.bat` | 只导出 BGM。 |
| `examples/extract_models_windows.bat` | 只导出模型、材质、贴图相关对象。 |
| `examples/extract_effects_windows.bat` | 只导出特效、动画、材质、贴图、prefab 和 rawfile 相关对象。 |

## 参数说明

| 参数 | 作用 |
| --- | --- |
| `--game-root "E:\...\game"` | 游戏根目录。脚本会自动找 `XzyLauncher_Data/yoo` 和 `XzyLauncher_Data/StreamingAssets/yoo`。 |
| `--yoo-root "E:\...\XzyLauncher_Data\yoo"` | 直接指定某一个 YooAssets 根目录。传了它就会覆盖 `--game-root`，因此只扫这一个根目录。 |
| `--source-layout all` | 使用 `--game-root` 时选择扫描来源。`all` 两个都扫，`hot` 只扫热更目录，`streaming` 只扫 StreamingAssets。 |
| `--out "E:\XZY\UI"` | 输出目录。不传时默认是当前目录下的 `xzy_assets_out`。 |
| `--packages Icon,Main,Spine` | 只扫描指定包。不传就是扫描所有包。 |
| `--categories ui,bgm,models,effects` | 只导出指定分类。不传就是所有分类都导出。可用分类包括 `ui`、`bgm`、`audio`、`models`、`effects`、`animation`、`prefabs`、`text`、`textures`、`materials`、`raw`、`other`。 |
| `--types Texture2D,Sprite,AudioClip` | 只导出指定 Unity 对象类型。不传就是所有类型都导出。 |
| `--limit 2` | 最多处理 2 个 bundle，适合测试。 |
| `--limit 0` | 不限制 bundle 数量，适合全量导出。 |
| `--execute` | 真的写出文件。不加这个参数就是 dry-run。 |
| `--no-export` | 只识别和解密 bundle，不让 UnityPy 导出内部对象。 |
| `--copy-rawfiles` | 复制本地 `.rawfile` payload 到 `assets/raw/<layout>/<package>/...`，并写入 `assets.csv`。它不会把 `.rawfile` 当 UnityFS bundle 解析。 |
| `--keep-bundles` | 保存解密后的 UnityFS bundle。 |
| `--workers 4` | 使用 4 个工作进程并行处理 bundle。默认 `1` 是串行模式。全量导出建议先试 `4`。 |
| `--progress-every 1` | 每处理 1 个 bundle 刷新一次进度，最直观。 |
| `--progress-every 0` | 关闭进度输出。 |
| `--progress-style bar` | 显示可视化进度条，默认值。安装了 Rich 时会使用更漂亮的样式，否则回退到纯文本。 |
| `--progress-style lines` | 每次刷新输出一行日志，适合保存日志。 |
| `--no-manifest-check` | 跳过本地 manifest/catalog 静态引用检查。 |
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
uv run python -m unittest discover -s tests
```

语法检查：

```bash
uv run python -m py_compile xzy_yooasset_extractor.py
```

## 开源和版权边界

本仓库使用 MIT License。MIT 只覆盖本仓库里的提取脚本、测试和文档，不覆盖任何第三方游戏资源。

请不要上传、发布或公开展示没有授权的图片、音频、模型、bundle、metadata 或其他可能受版权保护的内容。
## Windows 一键入口

- `run_all_windows.bat`：一键完整流水线，导出、Packet 侦查、表文本抽取、战斗配置导出、残余二进制探测、字符串探测和整理。
- `run_wizard_windows.bat`：分项导出和排障入口。
