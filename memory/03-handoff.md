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
- 除非用户要求，不要提交；但用户已设定发布打包例外：每次完成更新安装包打包后必须提交、推送、创建同版本 tag，并创建带安装包 asset 的 GitHub Release。

## 可能的下一步

- 如果做代码工作，从相关测试和 CodeGraph 上下文开始。
- 如果修改运行/数据行为，同步更新 `docs/specs/runtime-and-data-contracts.md`。
- 如果继续弹窗控制工作，先将 dated Superpowers design/plan 与当前源码和测试对比，再把漂移记录到 `memory/02-risks-blockers.md`。
- 如果继续 FSRS + SQLite 工作，先读 `docs/specs/settings-and-storage.md`、`docs/specs/study-scheduling.md` 和 dated plan `docs/superpowers/plans/2026-06-08-fsrs-sqlite-scheduling.md`；当前实现已接入 SQLite/FSRS 主路径，但 Windows 运行时检查仍需单独执行。
- 如果继续打包工作，编辑前检查 `build/`、`oh-my-word-py.spec` 和当前未跟踪安装器文件。当前轻量安装器已能生成带版本号的安装包，但真实安装/卸载交互仍需单独验证。用户已要求：每次完成更新安装包打包后，必须只提交本次发布相关变更、推送到 GitHub、创建同版本 tag，并创建带安装包 asset 的 GitHub Release；默认不要提交 `dist/` 产物或无关 dirty 文件。如果 `gh`/token/网络/权限不可用，报告失败原因并给出手动 `gh release create/upload` 命令。
- 如果继续 VoxCPM TTS 工作，当前目标是本机 optional companion process：主程序设置支持 `system_qt` 和 `voxcpm_local`，VoxCPM 通过本地 HTTP endpoint 调用 `tools/voxcpm_service`，安装器入口默认关闭且失败不应影响主安装。仍需在安装了 service-only 依赖和模型的机器上验证真实 VoxCPM 合成播放，以及安装器勾选 VoxCPM 后的长耗时部署交互。
- 如果继续 VoxCPM 应用内管理工作，重点文件是 `app/voxcpm_service.py`、`app/settings_window.py`、`app/controller.py`、`app/models.py`、`app/settings.py`、`build/build_exe.ps1` 和 `oh-my-word-py.spec`。当前策略是设置页后台安装/启动/停止，`voxcpm_auto_start` 仅在使用时启动已安装服务，不自动安装。
- 如果继续 2026-06-18 这轮 VoxCPM2 分包工作，先看 `docs/superpowers/specs/2026-06-18-voxcpm2-modelscope-download-design.md`、`docs/superpowers/plans/2026-06-18-voxcpm2-modelscope-download.md`、`app/voxcpm_runtime.py`、`app/voxcpm_service.py`、`app/controller.py`、`app/settings_window.py` 与 `tests/test_voxcpm_runtime.py` / `tests/test_voxcpm_service_manager.py`。当前代码已支持运行时包和模型包拆分、ModelScope 下载、手动导入模型包，但真实 ModelScope 仓库常量尚未端到端验证，且下载仍在 UI 线程同步执行。
- 如果继续 2026-06-18 这轮自动朗读工作，先看 `docs/superpowers/specs/2026-06-18-popup-auto-pronounce-design.md`、`docs/superpowers/plans/2026-06-18-popup-auto-pronounce.md`、`app/controller.py`、`app/settings_window.py`、`app/settings.py`、`app/models.py` 和对应 `tests/test_settings.py` / `tests/test_settings_window.py` / `tests/test_controller.py`。当前策略是默认关闭自动朗读，并由 controller 的单次 `QTimer` 在弹窗展示后延迟触发、在词变化或手动朗读时取消。
- 如果继续朗读文本/听感工作，重点文件是 `app/pronunciation.py`、`app/tts.py`、`tools/voxcpm_service/server.py`、`tools/voxcpm_service/engine.py`、`app/controller.py`、`app/overlays/card_popup.py`、`app/overlays/barrage_popup.py`、`app/settings_window.py` 和对应测试。当前默认 `word_and_example` 会生成 `word.\n\nexample_sentence`；VoxCPM 优先走 `/synthesize_stream` + `QAudioSink` 流式 PCM，完整 WAV 作为 fallback，并使用 4 个缓存文件轮换。
