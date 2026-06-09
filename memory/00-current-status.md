# 当前状态

## 文件职责

本文件记录当前执行状态和最近的工作区观察。稳定产品含义与契约仍由 `README.md`、`docs/` 和 `docs/specs/` 负责。

## 当前判断

- 本仓库是一个 Windows-first 的 Python 3.11 + PySide6 桌面背单词应用。
- CodeGraph 已为 Python 源文件初始化，结构性代码导航应优先使用它。
- 本轮约束建立前，工作区中没有已跟踪的根目录 `AGENTS.md`。
- 仓库已包含 `docs/superpowers/` 下带日期的弹窗控制 plan/spec 文件。
- 不要把未勾选的 dated plan 步骤当作当前实现状态证明。实现状态必须通过源码、测试、CodeGraph 和运行时验证确认。
- 2026-06-08 观察到：在加入约束文件前，工作区已经存在许多未提交的源码/测试/build/docs 变更。除非有证据证明，否则都视为用户工作。

## 最近验证

- 2026-06-08 约束建立：新 guardrail 文件的读序/占位自查未发现未完成占位标记。
- 2026-06-08 约束建立：`py -3.11 -m pytest tests -q` 通过，结果为 46 个测试通过。
- 2026-06-08 文档中文化：仓库 Markdown 文档已改为中文说明，旧英文标题扫描无命中。
- 2026-06-08 文档中文化：`py -3.11 -m pytest tests -q` 通过，结果为 46 个测试通过。
- 2026-06-08 FSRS + SQLite 实现核验：`py -3.11 -m pytest tests -q` 通过，结果为 66 个测试通过。
- 2026-06-09 打包/安装器实现核验：`py -3.11 -m pytest tests -q` 通过，结果为 68 个测试通过。
- 2026-06-09 打包/安装器实现核验：`.\build\build_exe.ps1` 成功生成 `dist/oh-my-word-py/oh-my-word-py.exe`；`.\build\build_installer.ps1 -SkipPortableBuild` 成功生成 `dist/oh-my-word-setup.exe`。
- 2026-06-09 打包/安装器实现核验：安装器 payload 未包含 `storage/`，包含 `_internal/data/wordbooks/` 词库；未执行真实安装交互或卸载交互。
- 后续代码变更的默认完整验证命令仍为 `py -3.11 -m pytest tests -q`。
- 对 UI、托盘、热键或打包变更，还必须执行 Windows 运行时检查；如果没有执行，必须明确说明。

## 新 Agent 阅读路径

1. `AGENTS.md`
2. `memory/00-current-status.md`
3. `memory/01-recent-decisions.md`
4. `memory/02-risks-blockers.md`
5. `memory/03-handoff.md`
6. `README.md`
7. `docs/00-overview.md`
8. `docs/specs/00-specs-overview.md`

## 事实源

- Agent 规则：`AGENTS.md`
- 稳定文档入口：`docs/00-overview.md`
- 实现契约：`docs/specs/`
- 当前代码结构：CodeGraph 和源码文件
- 当前交接：`memory/03-handoff.md`
