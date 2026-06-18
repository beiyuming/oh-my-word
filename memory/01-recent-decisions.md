# 近期决策

## 文件职责

本文件记录会影响近期工作的有效决策。稳定 rationale 放在 `docs/`；精确行为放在源码和测试中。

## 有效决策

### 1. 使用分层约束模型

- `AGENTS.md` 负责 agent 行为。
- `docs/` 负责稳定项目文档。
- `docs/specs/` 负责实现契约。
- `memory/` 负责当前状态、风险和交接。
- CodeGraph/源码/测试负责当前实现形状。

### 2. CodeGraph 是结构导航默认工具

符号、调用者、被调用者、调用链和影响半径使用 CodeGraph。字面文本、文档内容或已确定文件内的精确内容，再使用原生 grep/read。

### 3. 桌面运行行为按 Windows-first 处理

应用使用 PySide6、托盘行为和原生全局热键。测试可以验证逻辑，但真实托盘/热键/弹窗声明需要 Windows 运行时检查。

### 4. 保护运行期数据和导入数据

`storage/` 是用户运行状态。`data/wordbooks/` 可能包含内置和导入数据。不要在未确认意图前删除、重新生成或提交大型导入/生成数据。

### 5. 普通工作不自动提交，发布打包必须提交、推送并创建 GitHub Release

- 普通开发、文档和排查工作，除非用户明确要求 staging、commit、push 或创建 PR，否则未来 agent 应保持变更未暂存、未提交。
- 用户已要求：每次完成“更新并重新打包安装包”后，必须执行一次 Git 提交、推送到 GitHub、创建同版本 tag，并创建 GitHub Release。
- 发布提交只能暂存本次发布相关的源码、测试、文档、版本号、更新日志和打包脚本，不能用 `git add .` 把无关 dirty 工作带入提交。
- 生成的 `dist/` 安装包、portable payload、`storage/`、`.venv`、VoxCPM 模型/缓存和其它机器相关产物默认不提交，除非用户明确要求。
- 安装包二进制随同版本 GitHub Release 发布：普通 Git 提交、branch push 和 tag push 成功后，还必须创建或更新同版本 Release，并上传带版本号的安装包附件；如果 `gh`/token/网络/权限不可用，必须报告失败原因和手动上传命令。

### 6. 安装包使用轻量 WinForms 安装器

- 不引入 Inno Setup 或 NSIS，当前安装器由 `build/build_installer.ps1` 生成 C# WinForms 程序并用系统 `csc.exe` 编译。
- 安装器必须允许用户选择安装目录，并提供桌面快捷方式、开始菜单快捷方式和安装后启动选项。
- 安装器和 portable payload 不打包本机 `storage/` 用户数据。
- 覆盖安装和卸载依赖 `install_manifest.txt` 管理应用文件，不应递归清空用户选择的已有目录。
- PyInstaller one-folder 下内置词库从 `_internal/data/wordbooks/` 读取，运行期 `storage/` 写到 `oh-my-word-py.exe` 同级目录。

### 7. TTS 初始化采用主线程延迟 warm-up

- `AppController.initialize()` 只轻量创建 `PronunciationService`，不在初始化阶段同步完成 `QTextToSpeech` backend 构造。
- `system_qt` 的 warm-up 由 `QTimer.singleShot` 延迟触发，状态分为 `not_initialized`、`initializing`、`ready`、`unavailable`。
- 用户在 TTS 未就绪时触发朗读，应走托盘提示；同一初始化阶段需要节流，避免重复刷屏。

### 8. VoxCPM 采用应用内可选管理，不随应用启动

- VoxCPM 仍是 optional companion process，不进入根 `requirements.txt`，也不把 `.venv`、模型权重或 Torch 打进主应用。
- 主安装包/portable payload 可以携带 `tools/voxcpm_service` service-only 文件，以支持本地 companion process 运行；旧的脚本式后台安装入口不再对普通用户暴露。
- 默认不随应用启动 VoxCPM。只有用户选择 `voxcpm_local` 并开启 `voxcpm_auto_start` 后，朗读时才尝试启动已安装的本地服务。
- 未安装时不静默下载数 GB 模型，只提示用户到设置页下载/导入运行时包。

### 9. 朗读内容由设置控制

- `pronunciation_content_mode` 控制朗读文本，默认 `word_and_example` 以兼容旧行为。
- `word_and_example` 使用 `word.\n\nexample_sentence`，用明确停顿降低 VoxCPM 忽略开头短词的概率。
- 卡片按钮、弹幕按钮和朗读热键都必须走同一个朗读文本 helper，避免三处拼接逻辑漂移。
- VoxCPM HTTP 播放缓存保持有限文件轮换，并在连续朗读前停止旧播放，避免 QtMultimedia 复用同一路径导致偶发无声。

### 10. VoxCPM 优先走流式 PCM

- `voxcpm_local` 默认优先调用 `/synthesize_stream`，service 使用 `generate_streaming()` 产生 `s16le` mono PCM chunk。
- 桌面端使用 `QAudioSink` 写入 PCM chunk，目标是首个 chunk 到达后开始播放，而不是等待完整 WAV 文件生成。
- `/synthesize` 完整 WAV 路径保留为旧 service 兼容 fallback，不作为首选路径。
- GPU 判断以 service venv 中 PyTorch/CUDA 和 VoxCPM 模型实际 module device 为准；本机验证结果为 `cuda:0`。

### 11. 安装包和设置页使用版本化发布记录

- 当前版本号来源为 `app/version.py`，当前值随发布递增；当前工作树版本为 `0.1.15`。
- `build/build_installer.ps1` 默认输出带版本号的安装包，例如 `dist/oh-my-word-setup-v0.1.15.exe`。
- 设置窗口必须包含“关于”页，显示当前版本和更新日志。
- 后续每次重新打包发布都应先更新版本号和更新日志，再构建安装包。
- 每次完成更新安装包打包后，还应以包含版本号的提交信息提交本次发布相关变更，推送到 GitHub，创建同版本 tag，并创建带安装包 asset 的 GitHub Release。
- VoxCPM 可选安装脚本需要自动探测可用 Python 运行时，优先使用兼容的 3.11+ 环境；设置页的 VoxCPM 检测动作必须先应用当前打开窗口中的待保存设置，再刷新服务状态。

### 12. 当前工作树版本以 `app/version.py` 为单一事实源

- 当前工作树版本值为 `0.1.15`。
- 设置页关于页、安装器默认输出名和发布标签都必须从同一个版本源派生，不能在 UI、脚本或文档中手写另一份“当前版本”。

### 13. 弹窗自动朗读默认关闭，由 controller 持有定时器语义

- 新增 `auto_pronounce_on_popup`，默认 `false`。
- 新增 `auto_pronounce_delay_seconds`，默认 `1.0` 秒，允许 `0.00` 到 `10.00` 秒。
- 自动朗读的调度、取消和“当前词是否已失效”的二次确认统一放在 `AppController`，不把行为下沉到 card/barrage overlay。

### 14. VoxCPM2 普通用户首选 ModelScope 分包下载，兼容路径继续保留

- 普通用户首选 `下载并导入运行时包`，由应用按固定仓库顺序下载 `runtime zip + model zip` 并顺序导入。
- 设置页额外提供 `下载并导入模型包`，用于运行时已就绪后的单独模型恢复或重下。
- 运行时包与模型包拆分；当前只维护 `cu130` 一套包，最低驱动要求 `580`。
- `导入 VoxCPM 运行时包` 与 `导入模型包` 作为手动下载后的兜底路径保留。
- 安装器不再提供 VoxCPM 下载/安装 UI；普通用户路径统一收口到设置页四个下载/导入入口。
- 对预构建运行时包的导入校验，不再依赖未启动服务的 `/health` 探活；当前以运行时 Python 导入 `service.server` 作为 staging 自检，并在导入后按当前设置重写 `start_service.ps1` / `healthcheck.ps1`。

### 15. VoxCPM 下载与导入都必须异步，不阻塞设置页

- 设置页里的 `下载并导入运行时包`、`下载并导入模型包`、`导入 VoxCPM 运行时包`、`导入模型包` 都必须立即返回 UI 线程。
- ZIP 校验、残留目录清理、解压、运行时自检和 ModelScope 下载都放在后台线程执行。
- 设置页状态区负责显示阶段性文案；操作进行中要禁用重复点击按钮，避免并发导入。
