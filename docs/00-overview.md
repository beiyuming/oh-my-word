# 文档总览

## 目的

本文件是项目稳定文档入口。它说明文档包结构、产品边界、事实源链条，以及 agent 在修改行为前应继续阅读哪些文件。

## 产品快照

`oh my word` 是一个 Windows-first 的背单词复习桌面应用，使用 Python 3.11 和 PySide6 构建。它主要从系统托盘运行，以卡片或弹幕弹窗展示单词，使用本地 JSON 设置、SQLite 学习状态和 FSRS 复习调度，加载基于目录的词库，并优先保持离线发音。

根目录 `README.md` 负责用户可见范围、默认命令、运行期文件、词库规则和打包说明。本总览不重复 README 的所有细节。

## 文档包

- `AGENTS.md`：仓库级 agent 执行规则。
- `README.md`：产品/运行总览和用户可见命令。
- `docs/00-overview.md`：稳定文档入口。
- `docs/architecture/module-boundaries.md`：模块分组、依赖方向和 spec 映射。
- `docs/specs/00-specs-overview.md`：实现契约索引。
- `docs/specs/runtime-and-data-contracts.md`：运行、存储、词库、UI 验证和打包规则。
- `docs/specs/*.md`：按代码模块群拆分的稳定实现契约。
- `docs/superpowers/`：带日期的实现计划和规格。将其视为任务历史或待执行计划上下文，不要当作已实现证明。
- `memory/`：当前状态、决策、风险和未来 agent 的交接说明。

## 事实源链条

1. 用户指令和 `AGENTS.md` 约束 agent 行为。
2. `README.md` 和稳定 docs 约束产品含义与受支持流程。
3. `docs/specs/` 约束实现层契约。
4. 源码和测试约束当前实现事实。
5. `memory/` 记录当前工作区状态、活跃风险和下一步检查点。
6. CodeGraph 回答当前代码结构问题；文档不应手动维护符号清单。

## 稳定边界

- 运行目标：Windows 桌面优先。
- UI 框架：PySide6。
- 应用入口：`main.py`。
- 应用源码：`app/`。
- 逻辑测试：`tests/`。
- 内置/导入词库：`data/wordbooks/`。
- 运行期用户数据：`storage/settings.json`、`storage/oh_my_word.sqlite3`、兼容旧文件 `storage/learning_state.json` 和 `storage/app.log`。
- 打包输出：`dist/`；这是生成产物，不是文档事实源。

## 阅读路径

主动实现时，先从 `AGENTS.md` 和 `memory/` 开始，再回到本文件寻找稳定文档路径。

涉及运行、存储、数据、UI、热键或打包变更时，阅读：

1. `docs/specs/00-specs-overview.md`
2. `docs/architecture/module-boundaries.md`
3. `docs/specs/runtime-and-data-contracts.md`
4. 相关模块 spec
5. 通过 CodeGraph 查看相关源码/测试

模块 spec 对应：

- 应用协调：`docs/specs/app-controller.md`
- 设置与存储：`docs/specs/settings-and-storage.md`
- 学习调度：`docs/specs/study-scheduling.md`
- 词库目录：`docs/specs/wordbook-catalog.md`
- 弹窗层：`docs/specs/popup-overlays.md`
- 托盘、热键与发音：`docs/specs/tray-hotkeys-tts.md`
- 打包与运行：`docs/specs/packaging-runtime.md`

涉及弹窗控制工作时，还要阅读：

1. `docs/superpowers/specs/2026-06-01-popup-controls-design.md`
2. `docs/superpowers/plans/2026-06-01-popup-controls.md`
3. `memory/02-risks-blockers.md` 中关于 dated plan 与当前代码漂移的记录

涉及 FSRS + SQLite 学习调度工作时，还要阅读：

1. `docs/specs/settings-and-storage.md`
2. `docs/specs/study-scheduling.md`
3. `docs/specs/popup-overlays.md`
4. `docs/superpowers/specs/2026-06-08-fsrs-sqlite-scheduling-design.md`
5. `docs/superpowers/plans/2026-06-08-fsrs-sqlite-scheduling.md`

## 文档规则

- 当前进度和交接细节放在 `memory/`，不要放在这里。
- 字段、状态、运行时契约放在 `docs/specs/`，不要放在宽泛叙事文档里。
- 模块边界和依赖方向放在 `docs/architecture/`。
- 部分验证或计划中的行为必须明确标注。
- 契约改变时，在同一个检查点更新对应 spec。
