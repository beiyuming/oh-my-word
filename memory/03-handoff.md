# 交接

## 下一个 Agent 的最短路径

1. 阅读 `AGENTS.md`。
2. 阅读四个 `memory/` 文件。
3. 阅读 `README.md` 和 `docs/00-overview.md`。
4. 在修改运行、存储、UI、词库或打包行为前，阅读 `docs/architecture/module-boundaries.md` 和 `docs/specs/00-specs-overview.md`。
5. 按修改区域阅读对应模块 spec，例如 `settings-and-storage.md`、`study-scheduling.md`、`popup-overlays.md`。
6. 结构性代码问题先用 CodeGraph，再考虑 grep/read 循环。
7. 编辑前运行 `git status --short`，因为工作区可能已经包含用户改动。

## 当前约束状态

- 根目录 agent 规则已建立在 `AGENTS.md`。
- 稳定 docs 从 `docs/00-overview.md` 开始。
- 模块边界从 `docs/architecture/module-boundaries.md` 开始。
- 实现 specs 从 `docs/specs/00-specs-overview.md` 开始。
- 运行和数据验证 guardrails 位于 `docs/specs/runtime-and-data-contracts.md`。
- 模块级稳定 specs 已按当前代码模块群拆分到 `docs/specs/`。
- 当前状态交接文件位于 `memory/`。

## 不要重复做的事

- 不要在文档中重建大范围代码清单；使用 CodeGraph。
- 不要假设未勾选 dated plan 任务一定未完成或一定已完成。
- 未经用户确认，不要删除 `storage/`、导入词库、构建输出或未跟踪安装器文件。
- 除非用户要求，不要提交。

## 可能的下一步

- 如果做代码工作，从相关测试和 CodeGraph 上下文开始。
- 如果修改运行/数据行为，同步更新 `docs/specs/runtime-and-data-contracts.md`。
- 如果继续弹窗控制工作，先将 dated Superpowers design/plan 与当前源码和测试对比，再把漂移记录到 `memory/02-risks-blockers.md`。
- 如果继续 FSRS + SQLite 工作，先读 `docs/specs/settings-and-storage.md`、`docs/specs/study-scheduling.md` 和 dated plan `docs/superpowers/plans/2026-06-08-fsrs-sqlite-scheduling.md`；当前实现已接入 SQLite/FSRS 主路径，但 Windows 运行时检查仍需单独执行。
- 如果继续打包工作，编辑前检查 `build/`、`oh-my-word-py.spec` 和当前未跟踪安装器文件。当前轻量安装器已能生成 `dist/oh-my-word-setup.exe`，但真实安装/卸载交互仍需单独验证。
