# 项目现状与后续开发路线

这份文档给人看，用来快速理解当前项目做到哪里、还能做什么、后续怎么继续开发。

## 当前项目一句话

这是一个本地 YooAssets/Unity 资源研究工具：能扫描本地游戏目录、解密 tail-16 XOR bundle、导出 Unity 常见对象、拆 Packet/raw 容器、解析表格 `.bin`、提取活动/UI/道具文本，并把战斗和业务表分类导出成 JSON/CSV/XLSX。

它不是通用 Unity 解包器，也不是资源发布工具。

## 当前能做什么

资源侧：

- 扫描 `XzyLauncher_Data/yoo` 和 `XzyLauncher_Data/StreamingAssets/yoo`。
- 判断 bundle 是明文 UnityFS、tail-16 XOR UnityFS、tail-16 XOR 非 UnityFS，还是 unknown。
- 对 tail-16 XOR UnityFS 做解密。
- 用 UnityPy 导出 `Texture2D`、`Sprite`、`AudioClip`、部分 raw/text 对象。
- 复制 `.rawfile` payload。
- 输出 `assets.csv`、`bundles.csv`、`manifest_refs.csv`、`summary.json`。

Packet/bin 侧：

- 拆 Packet/BattlePacket/Assembly/AnimationPacket 这类 raw 容器。
- 支持 AES-CBC 解密。
- 根据 manifest 推导 Packet IV 逻辑名。
- 解析 `GameTables.p`、`UiTables.p` 里的表格 `.bin`。
- 结合 `dump.cs` 恢复字段名。
- 抽取 CJK 文本和活动/UI 文案。
- 对非表格 `.bin` 做用途分类。

业务整理侧：

- `gameplay_tables/`: 角色、战斗、技能、弹药、伤害、子弹、Buff、天赋等。
- `classified_tables/`: 道具、活动、商城、匹配排位、系统全局、视觉引用、装备装载等。
- `organized/`: 面向浏览的业务索引。

工程侧：

- 依赖统一由 `uv` 管理。
- 有合成数据单元测试，不依赖真实游戏文件。
- Windows 下有一键入口和分项向导。

## 当前不能做什么

- 不能下载服务器上缺失的 bundle。
- 不能只靠 manifest 还原本地不存在的图片或模型。
- 不能保证静态 manifest `not_found` 的资源运行时一定不用。
- 不能直接写出游戏原生 `.prefab`。
- 不能完整替代 AssetStudio 的 FBX/OBJ 导出流程。
- 不能把所有 residual `.bin` 结构化成业务字段；目前一部分只做用途分类。

## 当前推荐运行方式

先安装依赖：

```bash
uv sync
```

如果 uv 扫描 Python 权限异常：

```bat
set UV_PYTHON=D:\Python\python.exe
uv sync
```

一键完整流程：

```bat
run_all_windows.bat
```

分项运行或排障：

```bat
run_wizard_windows.bat
```

已有导出缓存时，使用 wizard 模式 9 复用已有结果，不必重新跑主导出。

## 重要输出怎么看

主导出：

- `package_report.csv`: 哪些 package 有 bundle/rawfile/manifest。
- `bundles.csv`: 每个 bundle 的识别和解密状态。
- `assets.csv`: 每个 Unity 对象的类型、分类、导出路径、状态。
- `manifest_refs.csv`: 本地 manifest/catalog 静态引用线索。
- `summary.json`: 总览统计。

Packet/bin：

- `bin_probe/packet_extract_full_decoded/packets.csv`
- `bin_probe/packet_extract_full_decoded/packet_entries.csv`
- `bin_probe/table_bin_probe_named/table_bins.csv`
- `bin_probe/binary_probe_named/binary_bins.csv`

文本/配置：

- `table_texts_activity/table_texts.csv`
- `table_texts_all/table_texts.csv`
- `gameplay_tables/tables.csv`
- `classified_tables/tables.csv`
- `gameplay_tables/gameplay_tables.xlsx`
- `classified_tables/classified_tables.xlsx`

## 当前代码健康状态

最近验证命令：

```powershell
uv sync
uv run python -m py_compile xzy_yooasset_extractor.py tools\export_gameplay_tables.py tools\export_classified_tables.py tools\run_full_pipeline.py tools\probe_packets.py
uv run python -m unittest tests.test_export_gameplay_tables tests.test_export_classified_tables tests.test_run_full_pipeline
uv run python -c "import UnityPy, openpyxl, Crypto, rich; print('ok')"
```

最近结果：

- 依赖导入正常。
- 相关测试 `7 tests OK`。
- `uv.lock` 已生成，应提交。

本地残留：

- `.analysis_deps/` 是旧依赖目录，当前机器 ACL 异常导致无法删除。它被 `.gitignore` 忽略，不参与运行。

## 后续开发流程

每次新增功能建议按这个流程：

1. 先读 `agent.md`、`README.md`、`docs/zh-CN.md`、`docs/project-history.md`。
2. 用 `uv sync` 保证环境一致。
3. 写或更新合成数据测试，不要依赖真实游戏文件。
4. 小样本跑通工具。
5. 再用 `E:\XZYTool` 或用户指定目录做真实数据验证。
6. 更新 README、中文说明、历史文档或路线文档。
7. 最后跑 `uv run python -m unittest discover -s tests`。

## 路线图

### P0: 收口和交付质量

- 保持 README、中文说明、agent handoff、历史文档同步。
- 给 `run_all_windows.bat` 和 `run_wizard_windows.bat` 做一次真实双击测试。
- 清理或说明所有本地临时目录。
- 如果准备公开 GitHub，确认 `.gitignore` 不会漏真实资源。

### P1: Unity 2022.3 Prefab 重建

目标：从 `prefab_graph.json` 生成真正 Unity `.prefab`。

建议实现：

- 新建 Unity 2022.3 Editor 工程或 `unity_rebuilder/` 目录。
- Editor 脚本读取 sidecar manifest。
- 重建 GameObject 层级、Transform、MeshFilter、MeshRenderer、SkinnedMeshRenderer、Animator、Material、Texture 引用。
- 用 `PrefabUtility.SaveAsPrefabAsset` 写出 `.prefab`。
- 对缺失脚本/shader/材质使用占位并记录 warning。

验收：

- 能导入一个静态模型样本。
- 能导入一个角色 prefab 样本。
- Unity Console 无致命 missing reference。

### P2: 模型/动画导出补强

参考 AssetStudio：

- Mesh 可导出 OBJ。
- Animator 可导出 FBX。
- MonoBehaviour 可导出 JSON。

本项目可以选择两条路线：

- 继续基于 UnityPy 实现基础 OBJ/材质 sidecar。
- 或调用/参考 AssetStudio 的导出模型，保留 Python 工具负责分类和索引。

### P3: 表格和二进制 schema 深挖

优先研究：

- `ambiguous_signature` 表。
- `no_match` 表。
- `animation_state_skeleton`。
- `collision_like`。
- `GameBehavior*.p` 内部结构。

原则：

- 先做只读 probe 和 preview。
- 再做 schema 推断。
- 最后才输出业务 JSON。
- 不要为了好看而误命名字段。

### P4: 结果浏览体验

可以继续增强：

- 生成 HTML 报告。
- 给 `organized/` 增加搜索索引。
- 为角色、技能、活动、道具生成更直观的交叉引用。
- 让用户可以从角色 ID 跳到技能、伤害、子弹、Buff、表现资源。

## 发布到 GitHub 前检查

必须确认：

- 没有真实游戏资源。
- 没有 key。
- 没有 `dump.cs`。
- 没有 metadata。
- 没有 `E:\XZYTool` 导出内容。
- 没有 `.venv/`、`.uv-cache/`、`.analysis_deps/`。
- 有 `pyproject.toml` 和 `uv.lock`。
- 文档中路径仅作为示例。
- License 只覆盖代码，不覆盖第三方游戏内容。

