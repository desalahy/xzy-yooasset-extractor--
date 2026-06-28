# 项目历史文档

这份文档保存项目上下文、关键决策、已经踩过的坑和后续不要丢失的经验。它不是使用手册；使用命令优先看 `README.md` 和 `docs/zh-CN.md`。

## 1. 起点

项目从一个 Unity IL2CPP/YooAssets 游戏安装目录开始。最早的问题是判断 `global-metadata.dat` 和本地资源是否被加密，以及如何从 `dump.cs`、dummy dll、YooAssets 代码路径里恢复实际算法。

早期确认过的重点：

- `global-metadata.dat` 不是标准 Il2CppDumper 可直接处理的形态，需要结合游戏侧代码逻辑理解。
- `YooAssetsDecryptService.LoadAssetBundle` 把 `DecryptFileInfo` 中的信息转成 16 字节数组传给 `BundleStream`。
- 本地 YooAssets bundle 存在一种尾部 16 字节 XOR key 格式：真实 payload 在前，末尾 16 字节作为循环 XOR key。
- 解密后如果头部变成 `UnityFS`，即可按 Unity bundle 继续交给 UnityPy 或其他工具。

这个阶段形成了 `docs/algorithm.md` 里记录的算法说明。

## 2. 从单文件解密到批量导出

最初目标是测试 UI 导出，然后全量导出 UI 到 `E:\XZY\UI`。后续扩展为可以选择包、输出目录、分类、对象类型和是否执行写出。

关键设计：

- `--packages` 控制扫描哪些 YooAssets package。
- `--categories` 控制写出哪些业务分类，如 `ui`、`bgm`、`models`、`effects`。
- `--types` 控制 Unity 对象类型，如 `Texture2D`、`Sprite`、`AudioClip`。
- `--limit 0` 表示全量，不是 0 个。
- `--execute` 才实际写文件；不加就是 dry-run。

踩过的坑：

- 只扫 `XzyLauncher_Data/yoo` 会漏掉 `StreamingAssets/yoo` 里的大量内置资源。
- 用户看到原游戏 12G、导出只有约 2G 时，核心原因通常是扫描来源不完整，必须用 `--game-root` 让工具同时扫描 hot-update 和 streaming assets。
- `Background` 这类包可能只有 manifest/hash，没有本地 bundle。manifest 里能看到资源路径不代表本地就有对应图片。

## 3. Packet/bin 线

后续发现 `Assembly`、`BattlePacket`、`Packet`、`AnimationPacket` 等包里有非 UnityFS raw 容器。主导出不能只停在 Unity bundle，需要继续拆 rawfile/packet。

形成的工具：

- `tools/probe_packets.py`
- `tools/probe_table_bins.py`
- `tools/extract_table_texts.py`
- `tools/probe_binary_bins.py`
- `tools/probe_string_bins.py`

关键结论：

- Packet 加密使用 AES-CBC。
- AES key 来自游戏配置中的 `_GameConfig._EncryptKey` 文本。
- IV 可以由 Packet 逻辑名推导：逻辑名按 UTF-8 转字节，截断或补零到 16 字节。
- `RawFileBuildPipeline` manifest 可用于 hash 到逻辑名映射，例如 `GameTables.p`、`UiTables.p`、`GameBehavior.p`。
- 不建议默认使用 `--strict-decode` 做全量导出，因为一些已解密但未识别的 payload 会被保守保留为 `.encrypted`；全量研究时应落为 `.bin` 再做二级解析。

历史验证结果曾达到：

- 347 个 packet/raw 容器全部可解析。
- 65 个容器带加密标记。
- 19824 个内部条目落盘。
- 输出包含大量 `.json`、少量 `.bin`、`.cpmv`、`.dll`。
- 不启用 `--strict-decode` 时剩余 `.encrypted` 为 0。

## 4. 表格 `.bin` 和文本

Packet 里的很多 `.bin` 不是失败残留，而是表格二进制。工具通过行数、列数、列类型和列数据读出表，再结合 `dump.cs` 里的 `Table*.tData` / `UiTable*.tData` 结构体恢复字段名。

重要状态：

- `unique_signature`: 列类型签名唯一，字段名可信。
- `package_preferred`: 多个结构相同，但可结合 `GameTables` / `UiTables` 包名偏好选择。
- `ambiguous_signature`: 多个结构完全同签名，不能硬猜。
- `no_match`: 能解析成表，但当前 `dump.cs` 没有匹配结构。

不要把歧义表强行命名。保守输出候选比错误命名更好。

文本侧形成了两条常用输出：

- `table_texts_activity`: 活动/UI 重点文本。
- `table_texts_all`: 全量 CJK 文本索引。

用户关心的活动 UI 文案、道具名、说明文字、活动任务描述等，不一定在图片里，很多在 `UiTable*` 表里。

## 5. 玩法表和业务分类

为了解决“表已经出来了但很难找”的问题，项目增加了二次分类导出：

- `tools/export_gameplay_tables.py`
- `tools/export_classified_tables.py`

已验证输出：

- `E:\XZYTool\gameplay_tables`
  - 39 张表
  - 16130 行
  - 角色、技能、伤害、子弹、弹药、Buff、天赋、核心、配件等
- `E:\XZYTool\classified_tables`
  - 118 张表
  - 12439 行
  - 道具经济、活动任务、商城充值、匹配排位、视觉引用、系统全局、装备装载等

典型高价值表：

- `TableDamageIndex`
- `TableBulletIndex`
- `TableAmmoIndex`
- `TableBuffIndex`
- `TableTalentIndex`
- `TableCharacterIndex`
- `TableCharacterParameter`
- `UiTableItem`
- `UiTableActivityMission`
- `UiTableActivityProgressReward`
- `TableEquipmentIndex`

## 6. 残余 `.bin` 判断

经过 table probe 后剩下的 `.bin` 又做了二次指纹分类。历史结论是：大多数 residual `.bin` 已经能解释为动画、碰撞、Unity YAML meta、字符串列表或占位文件，不应再笼统说“还有很多没解包”。

典型分类：

- `animation_like`
- `animation_state_skeleton`
- `unity_yaml_meta`
- `collision_like`
- `binary_with_strings`
- `string_list`
- `tiny_placeholder`

`animation_state_skeleton` 说明它更像动作状态骨架或占位记录，不是图片、音频、模型漏导。

## 7. Prefab/模型路线

用户追问为什么没有看到可直接进 Unity 的人物 prefab。调研 AssetStudio 后的结论：

- AssetStudio README 强调的是 `Mesh -> obj`、`Animator -> FBX`、`MonoBehaviour -> json`。
- 模型通常从 Scene Hierarchy 或 Animator 视角导出。
- 这更像“Unity 可重新导入的资产包”，不是直接写回游戏原生 `.prefab`。

本项目当前路线：

- Python 阶段输出 object-level JSON。
- Python 阶段输出 bundle-level `prefab_graph.json`。
- 后续应由 Unity 2022.3 Editor 工程读取 manifest，用 `PrefabUtility.SaveAsPrefabAsset` 生成真正 `.prefab`。

不要在文档里声称 Python 当前已经完成 native prefab 重建。

## 8. 一键流水线

为了避免用户运行分项脚本后漏掉 table/text/classified 阶段，新增了：

- `tools/run_full_pipeline.py`
- `run_all_windows.bat`
- `run_wizard_windows.bat` 的模式 8/9

流水线顺序：

1. main asset export
2. Packet extraction
3. table `.bin` probe
4. activity table text extraction
5. all CJK table text extraction
6. binary `.bin` probe
7. gameplay table export
8. classified table export
9. business organization
10. optional string probe

模式 9 用于已有 `raw/`、`assets.csv`、`bundles.csv` 时跳过主导出，复用旧结果继续后续阶段。

## 9. 依赖迁移到 uv

用户明确要求虚拟环境全部用 `uv`，不要自己搞环境。

已做：

- 新增 `pyproject.toml`。
- 生成 `uv.lock`。
- 删除 `requirements.txt`。
- 移除 `--deps-dir`、`.runtime_deps`、`pip install --target` 路线。
- Windows bat 入口执行 `uv sync`，再用 `uv run python`。
- `openpyxl` 加入 uv 依赖，XLSX 导出不再需要手工安装。

本地注意：

- `.runtime_deps` 已删除。
- `.analysis_deps` 是旧依赖缓存，当前机器上存在 ACL 异常，连 `takeown` 对部分目录也拒绝访问。它被 `.gitignore` 忽略，代码不应引用它。

## 10. 不要丢失的禁忌

- 不要提交真实游戏文件、导出资源、key、`dump.cs`、metadata dump。
- 不要把 `not_found` 解释成“运行时一定没用”。
- 不要把所有 `.bin` 解释成“加密失败”。
- 不要把 `listed_only` 全部当垃圾；它可能是 UnityPy 暂不能导出的结构化对象。
- 不要把 `--progress-every 20` 解释成导出数量限制，它只是进度刷新频率。
- 不要只用 `--yoo-root XzyLauncher_Data/yoo` 做全量结论。
- 不要把 Python sidecar JSON 说成 native Unity prefab。
- 不要重新引入 `pip install -r requirements.txt` 或 `--deps-dir`。
- 不要硬猜 `ambiguous_signature` 表名。

