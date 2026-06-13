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
- 2026-06-09 例句展示与朗读文本修复：`py -3.11 -m pytest tests -q` 通过，结果为 73 个测试通过；未执行 Windows 桌面视觉检查或真实 TTS 听音检查。
- 2026-06-09 默认词库整理：`data/wordbooks/` 默认只保留 `zz_kaoyan_enriched.json` 和 `SOURCES.md`；增强词库覆盖 5528 条，缺音标 0，空/占位例句 0；`py -3.11 -m pytest tests -q` 通过，结果为 74 个测试通过。
- 2026-06-11 TTS 初始化改为主线程延迟 warm-up + 状态提示：`py -3.11 -m pytest tests -q` 通过，结果为 105 个测试通过；尚未执行 Windows 桌面运行时检查。
- 2026-06-13 VoxCPM 应用内管理：已新增设置页“发音”分类中的 VoxCPM 后台安装、启动、停止、检测和日志入口；已新增 `app/voxcpm_service.py` 管理独立安装目录、模型目录和本地服务进程；已新增 `voxcpm_install_root`、`voxcpm_model_cache_root`、`voxcpm_use_model_mirror`、`voxcpm_auto_start` 设置字段。
- 2026-06-13 VoxCPM 应用内管理验证：`py -3.11 -m pytest tests -q` 通过，结果为 127 个测试通过；`.\build\build_installer.ps1` 成功生成 `dist/oh-my-word-setup.exe`；portable payload 包含 `_internal/tools/voxcpm_service/`；打包后的 `dist\oh-my-word-py\oh-my-word-py.exe` 可启动并打开 `oh my word 设置` 窗口；本机 VoxCPM service 从 `%LOCALAPPDATA%\OhMyWord\voxcpm\start_service.ps1` 启动后 `/health` 正常，并成功生成 WAV。
- 2026-06-13 朗读内容模式与 VoxCPM 播放加固：新增 `pronunciation_content_mode`，设置页可选择只读单词、只读例句或单词加例句；默认 `word_and_example` 使用 `word.\n\nexample_sentence` 作为明确停顿，减少 VoxCPM 吞掉开头短词的概率；VoxCPM WAV 缓存改为 4 个固定文件轮换并在播放前停止旧音频。
- 2026-06-13 朗读内容模式验证：`py -3.11 -m pytest tests -q` 通过，结果为 135 个测试通过；PySide 设置窗口运行时检查确认“朗读内容”选项为“只读单词 / 只读例句 / 单词 + 例句”且可读回 `example`；`.\build\build_installer.ps1` 成功生成 `dist\oh-my-word-setup.exe`；打包后的 `dist\oh-my-word-py\oh-my-word-py.exe` 可启动，短启动检查后已关闭进程。未执行真实安装器点击安装/卸载，也未执行人工听音判断。
- 2026-06-13 VoxCPM 流式发音：service 新增 `POST /synthesize_stream`，使用 VoxCPM `generate_streaming()` 输出 `s16le` PCM chunk；桌面端 `VoxCpmHttpProvider` 默认优先走流式 endpoint，并通过 `StreamingPcmPlayer`/`QAudioSink` 边接收边播放，旧服务 404/405 时回退完整 WAV。
- 2026-06-13 VoxCPM 流式验证：`py -3.11 -m pytest tests/test_tts.py tests/test_voxcpm_service_files.py -q` 通过，结果为 35 个测试通过；`py -3.11 -m pytest tests -q` 通过，结果为 137 个测试通过；FastAPI TestClient fake model 验证 `/synthesize_stream` 返回 `48000/s16le` PCM；真实 VoxCPM 本地模型完整消费 `generate_streaming()` 得到 5 个 chunk，总音频约 0.8 秒，日志显示 `cuda/bfloat16`；真实 endpoint TestClient 返回 200 和 `s16le` PCM；`StreamingPcmPlayer` 用静音 PCM 初始化 `QAudioSink` 成功；`.\build\build_installer.ps1` 成功生成 `dist\oh-my-word-setup.exe`；打包后的 `dist\oh-my-word-py\oh-my-word-py.exe` 可启动，短启动检查后已关闭进程；portable payload 内的 `tools\voxcpm_service` 包含 `synthesize_stream`、`generate_streaming` 和 `s16le`。未做人工听音或真实安装器点击安装/卸载。
- 2026-06-13 选词加权随机：SQLite 主路径 `StudyStore.select_next_word()` 保持到期复习词、新词、未掌握旧词的池级优先级，但同一候选池内改为按待学习力加权随机，不再固定取字母序第一个词；待学习力权重考虑 overdue、difficulty、stability、lapses、unknown_count 和 show_count。
- 2026-06-13 选词加权随机验证：先新增失败测试 `tests/test_study_store.py::test_selects_due_card_by_learning_need_weight`，确认旧实现不接受 `rng` 且固定取第一个候选；实现后该测试通过，`py -3.11 -m pytest tests/test_study_store.py tests/test_words.py -q` 通过，结果为 25 个测试通过；`py -3.11 -m pytest tests -q` 通过，结果为 138 个测试通过。
- 2026-06-13 安装包刷新：在当前工作树上运行 `py -3.11 -m pytest tests -q` 通过，结果为 138 个测试通过；`.\build\build_installer.ps1` 成功刷新 `dist\oh-my-word-setup.exe`，文件大小 58,178,560 字节，修改时间 2026-06-13 19:36:52；构建后、短启动前检查 portable payload 包含 `_internal\tools\voxcpm_service\install_local.ps1` 和 `_internal\data\wordbooks\zz_kaoyan_enriched.json`，且未预打包 `dist\oh-my-word-py\storage`；打包后的 `dist\oh-my-word-py\oh-my-word-py.exe` 可启动，短启动 5 秒后已强制关闭，并按运行契约生成 `dist\oh-my-word-py\storage\app.log` 与 `oh_my_word.sqlite3`。未执行真实安装器点击安装/卸载。
- 2026-06-13 VoxCPM 当前服务检查：本机 `127.0.0.1:8808` 的 `/health` 返回 200，`/synthesize` 返回 200，但 `/synthesize_stream` 返回 404；端口进程命令行为 `python.exe -m uvicorn service.server:app --host 127.0.0.1 --port 8808`，说明当前正在运行的 companion service 仍不是支持流式 endpoint 的新版服务。重新安装主程序不会自动替换已存在并正在运行的 VoxCPM service；需要停止旧服务并通过设置页“后台安装 / 更新”或安装器 VoxCPM 选项刷新 service。
- 2026-06-13 v0.1.1 版本化与安装包：新增 `app/version.py` 作为单一版本源，当前版本 `0.1.1`；设置页新增“关于”分类显示当前版本和更新日志；安装器默认输出 `dist\oh-my-word-setup-v0.1.1.exe`，安装器窗口标题/主标题显示 v0.1.1。
- 2026-06-13 v0.1.1 打包边界：`build_exe.ps1` 和 `build_installer.ps1` 只打包 VoxCPM service-only allowlist：`install_local.ps1`、`server.py`、`engine.py`、`requirements.txt`、`README.md`；不再整目录打包 `tools/voxcpm_service/`，避免误带 `.venv`、模型、Torch/CUDA wheel、Hugging Face/ModelScope 缓存或 `__pycache__`。`install_local.ps1` 更新时会清空并刷新已安装的 `service/` 目录，并校验复制后的 `server.py` 包含 `synthesize_stream`。
- 2026-06-13 v0.1.1 验证：`py -3.11 -m pytest tests -q` 通过，结果为 143 个测试通过；`.\build\build_installer.ps1` 成功生成 `dist\oh-my-word-setup-v0.1.1.exe`，文件大小 58,173,952 字节，修改时间 2026-06-13 22:42:58；portable payload 中 `_internal\tools\voxcpm_service\` 仅包含 5 个 allowlist 文件，未包含 `__pycache__` 或 `.venv`，构建后短启动前未预打包 `storage`；打包后的 `dist\oh-my-word-py\oh-my-word-py.exe` 可启动，短启动 5 秒后已强制关闭。未执行真实安装器点击安装/卸载，也未执行 VoxCPM service 真实后台更新。
- 2026-06-13 v0.1.2 VoxCPM 首尾漏音处理：按 VoxCPM 官方 API 参数显式启用 `retry_badcase=True`、`retry_badcase_max_times=3`，默认 badcase ratio threshold 为 `4.0`；默认 `cfg_value` 降为 `1.5` 并允许通过环境变量微调；完整 WAV 和流式 PCM 都加入短首尾静音垫，降低短词起音/尾音被本机播放截断的概率。
- 2026-06-13 v0.1.2 验证：先新增失败测试确认 service 缺少 badcase 参数和首尾静音保护；实现后 `py -3.11 -m pytest tests\test_voxcpm_service_files.py tests\test_tts.py tests\test_version.py tests\test_settings_window.py -q` 通过，结果为 44 个测试通过；`py -3.11 -m pytest tests -q` 通过，结果为 144 个测试通过；`.\build\build_installer.ps1` 成功生成 `dist\oh-my-word-setup-v0.1.2.exe`，文件大小 58,176,000 字节，修改时间 2026-06-13 23:07:37；portable payload 中 `_internal\tools\voxcpm_service\` 仅包含 5 个 allowlist 文件，未预打包 `storage`；短启动 `dist\oh-my-word-py\oh-my-word-py.exe` 5 秒成功并生成 exe 同级 `storage\app.log` 和 `oh_my_word.sqlite3`。
- 2026-06-13 v0.1.2 本机 service 状态：构建后再次检查本机 `127.0.0.1:8808`，`/health` 返回 200，但 `/synthesize_stream` 仍返回 404，说明当前正在运行的 companion service 仍未被本轮打包自动替换。需要通过设置页“后台安装 / 更新”或运行新的 service-only 安装脚本刷新已安装 service 后，才能验证 v0.1.2 的流式和参数改动在本机实际生效。
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
