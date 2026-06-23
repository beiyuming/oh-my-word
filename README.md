# oh my word (Python)

一个 Windows-first 的 `oh my word` Python 便携重写版，技术栈为 `Python + PySide6`。

当前版本：`v0.1.20`。设置窗口的“关于”页会显示当前版本和更新日志。

## 范围

- 系统托盘优先
- 两种展示模式：`card` 和 `barrage`
- 离线发音优先
- 本地 JSON 设置与 SQLite 学习状态
- 基于目录的词库，内置考研词库
- 支持用户导入 JSON/CSV 词库，并可选下载推荐的 NETEM 词库
- 使用 FSRS 管理复习间隔和 stability/difficulty 字段
- 支持“稍后”跳过当前词，以及托盘“暂停 30 分钟”
- 可选使用本机 VoxCPM 本地服务作为发音引擎；默认仍使用系统 Qt 离线发音

## 目录结构

```text
main.py
app/
data/wordbooks/
storage/
build/build_exe.ps1
tests/
requirements.txt
```

## 从源码运行

1. 如有需要，先创建虚拟环境。
2. 安装依赖：

```powershell
py -3.11 -m pip install -r requirements.txt
```

3. 启动应用：

```powershell
py -3.11 main.py
```

应用会从系统托盘启动。首次启动会创建缺失的运行文件，并打开设置窗口。

## 默认热键

- `Ctrl+Alt+1`：按设置中的“朗读内容”朗读当前词条
- `Ctrl+Alt+2`：切换弹窗详情
- `Ctrl+Alt+3`：立即触发下一个单词
- `Ctrl+Alt+4`：将当前单词标记为已掌握

热键可在设置中修改：点击快捷键输入框后按下目标组合键即可。

## 运行期文件

- `storage/settings.json`
- `storage/learning_state.json`
- `storage/oh_my_word.sqlite3`
- `storage/app.log`

源码运行时，`storage/` 位于项目根目录；portable 或安装版运行时，`storage/` 位于 `oh-my-word-py.exe` 同级目录。

`settings.json` 只保存用户配置。`oh_my_word.sqlite3` 保存卡片学习状态、近期单词、FSRS 载荷、复习日志、稍后状态和全局暂停状态。`learning_state.json` 是旧版学习状态文件；如果存在，应用会在启动时兼容导入，不会删除它。

发音设置保存在 `settings.json` 中：`pronunciation_content_mode` 默认为 `word_and_example`，可在设置页选择只读单词、只读例句或单词加例句；`auto_pronounce_on_popup` 默认为 `false`，用于控制单词弹出后是否自动朗读；`auto_pronounce_delay_seconds` 默认为 `1.0` 秒，可在 `0.00` 到 `10.00` 秒之间调整，让用户先看一眼单词再开始播放；`tts_provider` 默认为 `system_qt`，可选值 `voxcpm_local` 表示调用用户本机的 VoxCPM companion process；`voxcpm_endpoint` 第一版只接受本地 HTTP 地址（默认 `http://127.0.0.1:8808`）；`voxcpm_timeout_seconds` 默认为 15 秒。VoxCPM 相关设置还包括 `voxcpm_install_root`、`voxcpm_model_cache_root`、`voxcpm_use_model_mirror`、`voxcpm_auto_start`、`voxcpm_voice_prompt`、`voxcpm_stream_prebuffer_seconds`、`voxcpm_stream_prebuffer_max_wait_seconds`，以及可编辑的 `voxcpm_modelscope_namespace`、`voxcpm_modelscope_repository`、`voxcpm_modelscope_runtime_filename`、`voxcpm_modelscope_min_driver_version`，用于设置页下载/导入预构建运行时包、单独下载并导入模型包、查看 runtime ID / CUDA / 最低驱动 / 模型版本等元信息、控制使用时自动启动，以及调整流式 PCM 播放预缓冲。`voxcpm_stream_prebuffer_seconds` 默认 0.35 秒，可在设置页调整为 0.00 到 2.00 秒；`voxcpm_stream_prebuffer_max_wait_seconds` 默认 2.0 秒，到点后如果已经收到有效 PCM 会先开播，避免慢 GPU 为攒满目标音频秒数而额外等待过久。

设置页“发音”分类中的 `VoxCPM 高级参数` 默认折叠，面向需要调校本地模型的用户。该区域会持久化并传递给 companion service：`voxcpm_device`（`auto` / `cuda` / `cpu`）、`voxcpm_optimize`、`voxcpm_cfg_value`、`voxcpm_inference_timesteps`、`voxcpm_retry_badcase`、`voxcpm_retry_badcase_max_times`、`voxcpm_retry_badcase_ratio_threshold`、`voxcpm_leading_silence_seconds` 和 `voxcpm_trailing_silence_seconds`。默认值沿用当前兼容优先策略：设备 `auto`、`optimize=false`、`cfg_value=1.5`、`inference_timesteps=10`、badcase 重试开启且最多 3 次。

设置窗口的“帮助”分类内置 VoxCPM 参数操作文档，说明每个参数的用途、建议范围、慢 GPU 调参顺序，以及旧 service 不支持流式接口时的完整 WAV fallback 行为。

## 词库

应用会按文件名顺序加载 `data/wordbooks/` 下的所有 JSON 文件。

- 后加载文件会覆盖更早文件中的重复单词。
- 损坏的 JSON 文件会被跳过并写入日志。
- 如果没有可用词库，应用会重新创建默认的 `kaoyan_core.json`。
- 当前仓库默认只保留 `zz_kaoyan_enriched.json` 作为完整考研词库，覆盖 5528 个词条，并提供音标和例句；来源见 `data/wordbooks/SOURCES.md`。
- 设置页可以导入本地 JSON 或 CSV 词库，并转换为应用的本地 JSON 格式。
- 设置页可以在确认弹窗后下载推荐 NETEM 词库；确认弹窗会显示来源、许可证和目标路径。

每个词条使用以下形状：

```json
{
  "word": "abandon",
  "ipa": "/əˈbændən/",
  "part_of_speech": "verb",
  "definitions": ["放弃", "抛弃"],
  "example_sentence": "Many exam takers refuse to abandon their daily review plan.",
  "example_translation": "很多考研学生不会放弃每天的复习计划。"
}
```

导入的 JSON 可以使用上述精确形状，也可以使用常见替代字段，例如 `word`、`term`、`wordHead`、`translation`、`definitions`、`tranCn`，以及嵌套的 `content` 对象。导入的 CSV 文件至少应包含一个单词列（如 `word`、`term` 或类似字段）和一个释义/翻译列。

推荐下载源：

- 来源：`https://github.com/exam-data/NETEMVocabulary`
- 原始数据：`https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json`
- 词库许可证：`CC BY-NC-SA 4.0`
- 本地目标：`data/wordbooks/kaoyan_full.json`（可选下载文件，不是当前默认内置词库）

## 测试

运行逻辑测试：

```powershell
py -3.11 -m pytest tests -q
```

当前测试套件主要覆盖：

- 设置规范化与持久化
- SQLite 学习状态、旧 JSON 导入和 FSRS 复习写入
- 词库加载与选择规则
- 调度器纯逻辑

## 构建 EXE

```powershell
.\build\build_exe.ps1
```

该脚本使用 `PyInstaller`，并将打包输出放到 `dist/` 下。

打包产物只内置应用代码和 `data/wordbooks/` 词库，不内置本机 `storage/` 用户运行数据；首次启动时应用会在 exe 同级目录按需创建缺失的运行期文件。

## 构建安装包

```powershell
.\build\build_installer.ps1
```

该脚本会先构建 portable 版本，再生成带版本号的安装包，例如当前版本输出为 `dist/oh-my-word-setup-v0.1.20.exe`。安装包提供简单的 Windows 图形界面，允许用户选择安装目录，并可选择创建桌面/开始菜单快捷方式和安装完成后启动应用。

安装器会用安装清单管理应用文件。用户选择已有目录时，安装器不会递归清空整个目录；卸载脚本只删除清单中的应用文件和相关快捷方式。

安装器现在只负责主程序安装、快捷方式和卸载脚本；安装器不再提供 VoxCPM 的下载或安装入口。VoxCPM2 的运行时和模型统一在应用设置页完成下载或导入，避免安装器里的旧入口与当前 ModelScope 分包流程并存。

主安装器不会把 VoxCPM2 的重型运行时直接打进 payload。预构建运行时包和模型包会单独发布，当前主源为 ModelScope；GitHub Release 继续只放主安装器和说明文件。

安装完成后，可以在应用设置页的“发音”分类中优先使用 `下载并导入运行时包`，由应用按固定的 ModelScope 仓库顺序下载 `runtime zip + model zip` 并顺序导入。当前默认资源名为 `voxcpm2-runtime-win-x64-cu130-r2.zip`、`voxcpm2-model-cu130-r2.zip`，配套 checksum 文件为 `*.zip.sha256`。运行时包现在内置 self-contained portable Python（导入后落位为 `tts\voxcpm\python\python.exe`），目标机器不需要预装 Python。设置页同时提供 `下载并导入模型包`，用于运行时已就绪但模型目录缺失或需要重下模型时单独处理；也保留 `导入 VoxCPM 运行时包` 和 `导入模型包` 作为手动下载后的兜底路径。下载或导入期间任务会在后台线程执行，状态区会显示当前阶段，避免设置页长时间无响应。导入成功后状态区会显示 runtime ID、CUDA 标签、最低驱动要求和模型版本。设置页同时允许用户选择 VoxCPM 安装目录、模型目录、下载镜像开关，并提供检测、启动服务、停止服务和打开日志入口；点击这些按钮前会先应用当前窗口里已编辑的 VoxCPM 路径设置。`voxcpm_auto_start` 默认关闭；用户选择 `VoxCPM 本地服务` 并打开“使用时自动启动”后，应用会在朗读时启动已安装的本地服务。未安装时不会静默下载数 GB 模型，而是提示用户去设置页下载/导入运行时包。

## VoxCPM 本地发音

VoxCPM 不部署到云端服务器。桌面应用只通过 `127.0.0.1`/`localhost` 调用用户本机运行的 companion process：

```powershell
.\tts\voxcpm\start_service.ps1
```

导入后的运行时目录默认形态为 `tts\voxcpm\python\python.exe + tts\voxcpm\service\... + tts\voxcpm\models\VoxCPM2-local\...`；应用启动脚本会优先使用这个 portable Python，并继续兼容旧版 `.venv\Scripts\python.exe` 布局。

VoxCPM、PyTorch、CUDA、模型权重和相关依赖不进入根 `requirements.txt`，也不打包进主 EXE 或 portable payload。相关说明见 `tools/voxcpm_service/README.md`。
安装器路径会生成 `<软件安装目录>\tts\voxcpm\start_service.ps1`，用于以同一个模型缓存目录启动本地服务。设置页加载默认设置或旧版默认路径时，会按当前运行目录迁移为 `<软件运行目录>\tts\voxcpm` 和 `<软件运行目录>\tts\voxcpm\models`；用户手动选择的自定义目录不会被覆盖。
主程序仍只携带轻量 service-only 文件（`install_local.ps1`、`server.py`、`engine.py`、`requirements.txt`、`README.md`），不携带已导入的 portable Python 运行时、旧版 `.venv`、模型权重、Torch/CUDA wheel 或 Hugging Face/ModelScope 缓存。普通用户路径只包括设置页中的运行时/模型下载与导入；不点击这些入口时，不会下载模型或启动 VoxCPM 服务。

## VoxCPM2 运行时包环境要求

VoxCPM2 预构建运行时包不追求“任意 Windows 机器都能跑”，而是采用显式支持矩阵。当前面向：

- `Windows 10/11 x64`
- `NVIDIA GPU`
- 运行时包声明的最低驱动版本
- 推荐 `8 GB+ VRAM`
- 推荐至少 `15 GB+` 可用磁盘空间

普通用户首选在设置页点击 `下载并导入运行时包`，由应用从 ModelScope 下载与当前环境匹配的运行时包和模型包。若运行时已存在但模型目录缺失，也可以单独点击 `下载并导入模型包`。也可以手动下载后分别通过 `导入 VoxCPM 运行时包` 与 `导入模型包` 导入。导入成功后，运行时仍落在 `<软件目录>\tts\voxcpm`，并继续通过本地 `127.0.0.1` companion process 提供发音服务；当前预构建运行时包已自带 portable Python，不依赖宿主环境。

如果你的机器不在这个支持矩阵内，或者手头没有匹配的 runtime zip，当前版本不再提供旧的脚本式后台安装入口；这类环境建议继续使用 `system_qt` 发音，或等待对应矩阵的预构建运行时包。

VoxCPM provider 默认优先调用 `POST /synthesize_stream`，服务端使用 VoxCPM 的 `generate_streaming()` 输出 `s16le` PCM chunk，桌面端用 `QAudioSink` 边接收边播放，并按 `voxcpm_stream_prebuffer_seconds` 先预缓冲一小段 PCM 来降低句中卡顿；保存设置后会重建 VoxCPM TTS 后端，使新的预缓冲和最大等待时间立即用于后续朗读。旧服务不支持流式 endpoint 并返回 404/405 时，客户端会在日志中记录原因，并回退到 `POST /synthesize` 的完整 WAV 播放路径。流式路径会记录首字节耗时、达到预缓冲耗时、已缓冲音频秒数、总生成耗时和平均生成倍率；如果生成速度低于实时播放，会提示降低高级参数、改用完整 WAV 或增大预缓冲。service 使用设置页写入的环境变量控制 VoxCPM 设备、optimize、CFG、推理步数、badcase 重试和首尾静音；如果启用 optimize 后模型加载失败，service 会记录异常并用 `optimize=False` 重试，避免直接让应用崩溃。使用 `voxcpm_local` 时，应用会把独立单词包装为 `"word".` 再发送给 VoxCPM，以强化短词边界；单词加例句模式中单词和例句之间使用轻停顿空格，不再使用双换行强停顿；如果设置了 `voxcpm_voice_prompt`，应用会按 VoxCPM Voice Design 格式把提示词作为 `(prompt)` 前缀加到合成文本前。

## 备注

- 当前首版只面向 Windows。
- 全局热键使用 Windows 原生 `RegisterHotKey` API。
- 默认离线发音优先使用 `QtTextToSpeech`，并回退到任何可用的英语语音；VoxCPM 本地服务不可用时会失败并记录错误，不会自动声称朗读成功。
