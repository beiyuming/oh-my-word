# 仓库 Agent 规则

## 本文件职责

本文件是本项目中所有 agent 的仓库级执行契约。它定义阅读顺序、事实源边界、CodeGraph 使用方式、文档纪律、验证要求和 Git 行为。产品事实与实现契约分别由 `README.md`、`docs/`、`docs/specs/`、源码和测试负责。

## 正式回复头

在本仓库的正式最终回复中：

1. 第一行必须写：`已对接AGENTS约束`。
2. 第二行必须按以下格式列出本次使用的 skill、tool、plugin 和项目文档来源：
   `skills: xxx tools: xxx plugins: xxx docs: xxx`
3. 结论必须结构化、基于证据、可验证。信息不足时，先索要缺失证据，不要猜测。

## 工作前阅读顺序

在进行重要代码、文档、打包或行为变更前，按顺序阅读：

1. `AGENTS.md`
2. `memory/00-current-status.md`
3. `memory/01-recent-decisions.md`
4. `memory/02-risks-blockers.md`
5. `memory/03-handoff.md`
6. `README.md`
7. `docs/00-overview.md`
8. `docs/specs/` 下的相关文件
9. 如果任务涉及对应区域，阅读 `docs/superpowers/` 下的相关 dated plan/spec
10. 通过 CodeGraph 或定向文件读取查看当前代码和测试

很小的只读请求可以酌情处理，但在修改仓库前不能跳过该读序。

## 事实源边界

- 用户指令和本文件负责 agent 行为。
- 除非更具体的稳定文档或 spec 已经覆盖，`README.md` 是当前产品和运行方式总览。
- `docs/00-overview.md` 是稳定文档入口。
- `docs/specs/` 负责实现层契约：运行命令、存储形状、状态规则、数据契约和验证要求。
- `memory/` 负责当前状态、近期决策、已知风险和交接记录，不能变成重复的架构树。
- 源码和测试负责当前实现事实。需要结构信息时优先用 CodeGraph，需要精确内容时再定向读取文件。
- `storage/` 保存运行期用户数据。不要为了省事覆盖、删除或重新规范化它。
- `data/wordbooks/` 保存内置和导入词库。导入或下载数据必须保留来源和许可证说明。
- `build/`、`dist/`、`.pytest_cache/`、`.codegraph/` 以及生成的安装包载荷不是稳定产品规格。

## CodeGraph

本项目已配置 CodeGraph MCP server（`codegraph_*` tools）。CodeGraph 是基于 tree-sitter 解析的符号和调用图索引，可以返回 grep 无法直接提供的结构信息。

### 何时优先用 CodeGraph

结构性问题使用 CodeGraph：谁调用谁、改某个符号会影响什么、某个符号在哪里定义、函数签名是什么。字面文本、注释、日志消息或已确定文件内的精确内容，再使用原生 grep/read。

| 问题 | 工具 |
| --- | --- |
| X 在哪里定义 / 查找名为 X 的符号 | `codegraph_search` |
| 谁调用了 Y | `codegraph_callers` |
| Y 调用了什么 | `codegraph_callees` |
| X 如何到达/变成 Y，追踪 X 到 Y 的流 | `codegraph_trace` |
| 修改 Z 会影响什么 | `codegraph_impact` |
| 查看 Y 的签名、源码或 docstring | `codegraph_node` |
| 获取某个任务或区域的聚焦上下文 | `codegraph_context` |
| 一次查看多个相关符号源码 | `codegraph_explore` |
| 查看某个路径下有哪些文件 | `codegraph_files` |
| 检查索引是否健康 | `codegraph_status` |

### CodeGraph 使用规则

- 架构、功能或 bug 背景问题，先用 `codegraph_context`；需要源码时，再用一次 `codegraph_explore`。
- 具体流转问题，先用 `codegraph_trace`；需要函数体时，再用一次 `codegraph_explore`。
- 按符号名查找时不要先 grep。
- 不要对多个符号循环调用 `codegraph_node`，改用 `codegraph_explore`。
- 如果 CodeGraph 响应提示某些文件已过期，只读取提示中的具体文件。
- 如果 `.codegraph/` 不存在或 CodeGraph 报告未初始化，先问用户是否要运行 `codegraph init -i`。

## 文档纪律

- 仓库级 agent 行为只放在 `AGENTS.md`。
- 稳定产品、架构和实现总览放在 `docs/`。
- 字段、存储、状态、运行方式和验证契约放在 `docs/specs/`。
- 当前进度、近期决策、风险和交接记录放在 `memory/`。
- 不要把计划中的工作说成已实现。mock、占位、生成内容、部分集成和未验证行为必须明确标注。
- 不要在文档中维护大范围符号清单；当前代码形状由 CodeGraph 和源码负责。

## 检查点流程

非平凡工作按以下节奏推进：

1. 完成一个边界清晰的切片。
2. 如果契约改变，同步更新相关稳定文档或 spec。
3. 如果状态、风险或交接信息改变，同步更新 `memory/`。
4. 先运行最小有效验证，再按需要运行更完整的官方验证。
5. 汇报证据和限制。
6. 只有用户明确要求时才提交。

## 运行和验证

本项目是 Windows-first 的 Python 3.11 + PySide6 桌面托盘应用。

- 需要安装依赖时使用：`py -3.11 -m pip install -r requirements.txt`
- 从源码运行：`py -3.11 main.py`
- 运行完整测试：`py -3.11 -m pytest tests -q`
- 构建 Windows 包：`.\build\build_exe.ps1`
- 对 PySide UI、悬浮窗、托盘、全局热键或打包行为的完成声明，不能只依赖测试。还必须在 Windows 上启动应用或构建产物并记录实际检查内容；如果没有做运行时检查，必须明确说明。
- 对词库导入/下载行为，要验证数据形状、重复词覆盖顺序、坏 JSON 处理、来源和许可证标注。

## 自动化和 AI 边界

- AI 或脚本可以起草文档、测试、UI 和数据转换，但生成内容在被源码、测试或人工确认的文件变更接纳前，始终只是候选内容。
- 不要把 provider 凭据、密钥或机器特定路径写入可跟踪的 UI/前端代码或文档。
- 不要让 `storage/` 下的本地运行文件成为正式产品事实源。
- 网络下载、依赖安装、安装包构建和破坏性文件操作必须有明确目的；沙箱或策略要求时必须请求批准。

## Git 纪律

- 除非用户要求，不要提交、建分支、推送或创建 PR。
- 除非用户明确要求，不要改写历史。
- 不要回滚或删除用户工作。遇到无关 dirty 文件时保持原样。
- 如果需要编辑的文件已有用户改动，先理解现状并做窄范围修改。

## 冲突处理

当指令、文档、测试和代码冲突时：

1. agent 行为优先遵循最高权威的用户/仓库指令。
2. 当前实现事实优先看源码和测试。
3. 预期实现契约优先看 `docs/specs/`。
4. 未解决的漂移记录到 `memory/02-risks-blockers.md`。
5. 只有无法做出安全窄假设时才询问用户。

## 项目文档入口

- 稳定总览：`docs/00-overview.md`
- Specs 索引：`docs/specs/00-specs-overview.md`
- 运行与数据契约：`docs/specs/runtime-and-data-contracts.md`
- 当前状态：`memory/00-current-status.md`
- 交接说明：`memory/03-handoff.md`
