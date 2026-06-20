# 风险与阻塞

## 当前硬阻塞

- 纯文档约束工作目前没有已知硬阻塞。

## 已知风险

### 1. 工作区已有 dirty 状态

- 风险：2026-06-08 观察到许多源码/测试/build/docs 文件已经修改或未跟踪。
- 影响：未来 agent 可能意外覆盖用户工作，或误判变更归属。
- 处理：编辑前运行 `git status --short`，保持 patch 窄范围，不回滚无关文件。发布打包后的强制提交/推送也必须只暂存本次发布相关文件，不能用 `git add .` 吸收既有 dirty 工作。

### 2. Dated popup-control docs 可能与实现漂移

- 风险：`docs/superpowers/plans/2026-06-01-popup-controls.md` 包含未勾选任务，而源码/测试可能已经包含相关变更。
- 影响：agent 可能把计划状态误认为实现状态。
- 处理：dated docs 只作为意图参考。当前行为必须通过 CodeGraph、源码/测试和运行时检查验证。

### 3. UI 行为无法完全靠单元测试验证

- 风险：PySide 托盘、弹窗位置、全局热键和打包可执行文件存在测试覆盖不到的运行时行为。
- 影响：变更可能通过测试，但在 Windows 桌面运行时失败。
- 处理：UI/热键/打包工作完成前，运行测试并执行 Windows 运行时检查。

### 4. 导入/生成词库和安装器产物

- 风险：工作区可能包含生成的安装器文件或导入词库。
- 影响：agent 可能无意提交大型文件或许可证敏感文件。
- 处理：添加生成包、安装器载荷或外部词库数据前，先确认是否应被跟踪。更新打包后的发布提交默认不包含 `dist/` 安装包、portable payload、模型缓存或其它生成产物。

### 5. 安装器交互尚未真实执行

- 风险：安装器已成功编译并检查 payload，但尚未在 Windows 桌面上实际点选安装目录、安装、启动和卸载。
- 影响：快捷方式创建、安装后启动和卸载脚本仍可能存在只能通过真实交互发现的问题。
- 处理：发布前在一个临时安装目录执行完整安装/卸载检查，避免选择包含用户文件的目录。

### 6. VoxCPM 应用内安装/启停仍需干净机器验证

- 风险：设置页已接入后台安装和服务启停，并已在当前机器验证已安装服务的 `/health` 与一次合成请求；但干净机器上的真实下载安装、长时间模型下载、PowerShell 策略、GPU/CPU 环境差异仍无法完全靠当前单元测试覆盖。
- 影响：普通用户机器上可能遇到下载超时、PowerShell 策略、CUDA/Torch 兼容或日志路径问题。
- 处理：发布前建议在干净临时目录执行设置页后台安装流程；至少验证未安装提示、安装日志生成、启动服务、`/health`、一次合成请求和停止服务。

### 7. VoxCPM 朗读听感仍需人工听音

- 风险：已通过文本生成规则、缓存轮换和流式 PCM 路径降低“开头单词偶发听不到”和长句等待完整 WAV 的问题，但没有在本轮执行人工听音对比。
- 影响：不同 GPU/CPU、驱动、模型版本或声卡环境下，VoxCPM 仍可能对短词起音处理不稳定。
- 处理：发布前建议用 `word_and_example`、`word`、`example` 三种模式各朗读多次，确认短词起音、流式首响和连续点击播放都符合预期。

### 8. 旧 VoxCPM companion service 可能继续占用 8808

- 风险：2026-06-13 检查到本机 8808 上运行的是 `python.exe -m uvicorn service.server:app`，`/health` 和 `/synthesize` 可用，但 `/synthesize_stream` 返回 404。
- 影响：即使主程序已打包支持流式，客户端也会回退完整 WAV，用户仍会感到每次朗读卡几秒；短词吞音问题也不会因主程序重装自动消失。v0.1.2 已加入 VoxCPM badcase 参数和首尾静音保护，但这些改动必须进入已安装的 service 才会生效。
- 处理：v0.1.3 已让设置页停止服务可以识别并停止同一 local endpoint 上命令行为 `uvicorn service.server:app` 的旧 VoxCPM 进程，同时避免误杀无关端口进程。之后仍需要通过设置页重新下载/导入运行时包并重启服务，确保 companion service 已刷新。刷新后必须重新验证 `/synthesize_stream` 返回 200，再做人工听音。

### 9. 安装器脚本在 PyInstaller 结束后可能遇到瞬时文件锁

- 风险：2026-06-17 首次执行 `.\build\build_installer.ps1` 时，PyInstaller 已完成，但 `Compress-Archive` 打包 portable payload 时命中 `dist\oh-my-word-py\_internal\base_library.zip` 被占用，导致脚本失败。
- 影响：同一轮发布里首次一键打包可能偶发失败，即使 portable 产物本身已经构建成功。
- 处理：本轮通过复用已生成的 portable 产物执行 `.\build\build_installer.ps1 -SkipPortableBuild` 成功绕过。后续若继续复现，应给安装器脚本增加 zip 重试或文件锁等待逻辑，而不是把这类瞬时失败当成真正的构建失败。

### 10. 已发布的 v0.1.9 安装器资产仍缺少最新两次 Python runtime 修复

- 风险：当前远端 `v0.1.9` Release/安装器资产是在修复 `Get-PythonRuntimeCandidate` 空参数数组绑定错误，以及 `Resolve-PythonRuntime`/调用端双重数组包装错误之前构建的；本地最新 `dist\oh-my-word-setup-v0.1.9.exe` 已包含这两次修复，但尚未覆盖远端 `.9` 资产。
- 影响：目标机器既可能在探测 `python` / `python3` 候选时命中 `Arguments` 为空数组的 PowerShell 绑定异常，也可能在探测到多个 Python 候选时把数组对象误传给 `Invoke-Native -FilePath`，出现 `Using Python runtime: py -3.11 py -3 python` 这类异常日志。
- 处理：在用户确认本轮修复完成并决定如何处理现有 `v0.1.9` Release 前，不要再递增版本号；后续覆盖现有 `.9` 资产时，要基于本地最新打包结果执行受控提交/推送/更新 tag 或 release asset，并明确说明远端旧资产曾包含哪两类安装脚本缺陷。

### 11. ModelScope 线上资产已验证，但设置页真实点击链路仍待手工回归

- 风险：2026-06-19 已确认真实线上 `voxcpm2-runtime-win-x64-cu130-r2.zip` / `voxcpm2-model-cu130-r2.zip` 及其 `*.sha256` 可下载、校验匹配，并在隔离目录跑通 `runtime 导入 → model 导入 → start_service() → /health`；2026-06-20 又修复了应用内下载仍指向旧 ModelScope `api/v1` URL、以及 blocking helper 误判成功的问题。但这些验证仍主要走代码级/测试级路径，不是打包后设置页上的真实按钮点击。
- 影响：核心下载/导入/启动逻辑和魔搭资产本身已被验证；若用户后续仍在新版本上遇到“下载失败”或“导入失败”，优先怀疑本地旧安装残留、客户端版本落后，或 GUI 线程/对话框层面的额外交互问题，而不是继续怀疑线上 `r2` 包内容或下载地址本身。
- 处理：后续最好在打包产物上再手工点一次设置页的 `下载并导入运行时包` / `下载并导入模型包` / `启动服务`，把 GUI 层也闭环；若继续出现问题，应直接抓 `storage\app.log` 与 `install.log`，而不是重新怀疑魔搭资产布局或 URL 形态。

### 12. VoxCPM 下载/导入虽然已异步，但进度仍只有阶段文本

- 风险：`下载并导入运行时包`、`下载并导入模型包`、`导入运行时包`、`导入模型包` 现在都已放到后台线程，不再卡死设置页；但当前 UI 只展示“校验 / 清理 / 解压 / 自检 / 激活”这类阶段文案，没有按字节数更新的百分比。
- 影响：大包导入时虽然窗口不再假死，但用户仍无法准确判断剩余时间，也无法区分“正在删旧 staging”与“正在解压大 zip”耗时差异。
- 处理：后续可以把 `_download_url_to_path(..., on_chunk=...)` 的字节进度继续上抛到设置页，并为本地 zip 导入补压缩包大小/文件计数级进度。

## 普通不确定性

- 仓库还没有为每个领域建立专用 spec。只有在契约变化或未来 agent 确实需要时，才新增聚焦 spec。

## 建议复查的稳定文档

- `docs/00-overview.md`
- `docs/specs/00-specs-overview.md`
- `docs/specs/runtime-and-data-contracts.md`
- `README.md`
