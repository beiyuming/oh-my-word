# 打包与运行契约

## 范围

本 spec 约束源码运行、PyInstaller 打包、安装器脚本和运行时检查。涉及 `main.py`、`requirements.txt`、`build/` 和 `oh-my-word-py.spec`。

## 源码运行

目标环境：

- Windows 优先。
- Python 3.11。
- PySide6。

安装依赖：

```powershell
py -3.11 -m pip install -r requirements.txt
```

源码运行：

```powershell
py -3.11 main.py
```

## 测试

完整测试命令：

```powershell
py -3.11 -m pytest tests -q
```

测试不得依赖真实 `storage/` 用户数据。需要存储状态时使用临时目录。

## 打包

当前 PyInstaller 打包命令：

```powershell
.\build\build_exe.ps1
```

打包由 `oh-my-word-py.spec` 和 build 脚本驱动。`dist/` 是生成输出，不是稳定事实源。

打包载荷包含应用代码、依赖、`data/` 内置词库，以及用于应用内后台安装 VoxCPM 的 `tools/voxcpm_service` service-only 脚本。不得把本机 `storage/` 运行期用户数据打进 portable 包或安装器 payload。PyInstaller one-folder 构建中，内置词库可以位于 `_internal/data/wordbooks/`，VoxCPM service-only 脚本可以位于 `_internal/tools/voxcpm_service/`；运行期 `storage/` 必须位于 `oh-my-word-py.exe` 同级目录。首次启动负责创建缺失的运行期存储文件。

`build/` 可能包含脚本和生成中间物。添加安装器文件前必须确认是否应跟踪，避免误提交大型或机器相关产物。

当前安装包构建命令：

```powershell
.\build\build_installer.ps1
```

安装包默认输出为带版本号的文件名，例如 `dist/oh-my-word-setup-v0.1.5.exe`。版本号必须来自代码内单一版本源，并同步显示在安装器窗口标题/主标题和设置页关于/更新日志中；后续每次重新打包发布都必须递增或明确维护版本号和更新日志。安装器由 build 脚本生成 C# WinForms 程序并用系统 `csc.exe` 编译，必须允许用户选择安装目录，并提供桌面快捷方式、开始菜单快捷方式和安装完成后启动应用的选项。

每次“更新并重新打包安装包”完成后，发布流程必须执行一次 Git 提交、推送到 GitHub、创建同版本 tag，并创建 GitHub Release。提交前必须完成对应验证，并只暂存本次发布相关的源码、测试、文档、版本号、更新日志和打包脚本；不得因工作区已有 dirty 状态而把无关文件带入提交。生成的 `dist/` 安装包和 portable payload 默认仍是构建产物，不进入 Git 提交；只有用户明确要求跟踪某个发布产物时才可以暂存。提交信息应包含版本号，例如 `release: v0.1.5`；tag 应使用同一版本号，例如 `v0.1.5`。

安装包二进制必须随同版本 GitHub Release 发布，而不是依赖普通 `git push`。发布提交、branch push 和 tag push 成功后，应创建或更新同版本 Release，并上传带版本号的安装包附件，例如 `dist/oh-my-word-setup-v0.1.5.exe`。如果 `gh` 未安装/未登录、token 缺失、网络或权限导致 Release 附件上传失败，完成报告必须说明失败原因、已推送的 commit/branch/tag 状态、安装包本地路径，并给出可手动执行的 `gh release create` 或 `gh release upload --clobber` 命令。

安装器不得在用户选择的目录已存在时递归删除整个目录。覆盖安装应先检查运行中的旧应用；如果目标安装目录的 `oh-my-word-py.exe` 仍在运行，安装器必须提示用户关闭应用后重试，不应继续删除清单文件并暴露 DLL 占用导致的底层权限异常。覆盖安装应只删除上一次安装清单记录的应用文件，再写入新 payload。卸载脚本也应只删除安装清单中的应用文件、安装器创建的快捷方式，以及已经变空的应用目录。

安装器可以提供 `Install local VoxCPM pronunciation engine` 可选项，但该选项必须默认关闭。VoxCPM 本地设置只作为安装后的可选 companion process 部署步骤运行，目标目录应位于用户可写目录，例如 `%LOCALAPPDATA%\OhMyWord\voxcpm`。安装器必须允许用户选择 VoxCPM engine 目录和模型缓存目录；模型缓存默认 `%LOCALAPPDATA%\OhMyWord\voxcpm\models`，并通过 `ModelCacheRoot` 传给 `install_local.ps1`。安装器必须提供 `Use model download mirror` 选项并默认启用；镜像模式必须优先使用 ModelScope，失败时回退到 hf-mirror；用户关闭该选项时才直连 Hugging Face。脚本必须据此设置 `HF_HOME` 和 `HF_HUB_CACHE`，不要依赖或污染全局 Hugging Face 默认缓存目录。安装器启动 VoxCPM setup 前必须预检这些目录并在父级可写时自动创建；如果无法创建，应提示用户选择可写位置。安装器运行 VoxCPM setup 时必须捕获 PowerShell stdout/stderr 到 bootstrap log；即使 `install.log` 未生成，也应给出可查看的诊断日志路径。该步骤可以创建独立 venv、安装 service-only requirements 并检查模型，但不得把 VoxCPM、PyTorch、CUDA、模型权重或 `.venv` 放入主 portable payload、根 `requirements.txt` 或主应用 EXE。VoxCPM 设置失败时必须提示日志位置，并且主应用安装仍视为成功。

安装后的主应用还必须能从设置页发起 VoxCPM 后台安装/更新，因此 portable payload 和安装器内嵌的 VoxCPM payload 只能包含轻量 service-only 文件：`install_local.ps1`、`server.py`、`engine.py`、`requirements.txt`、`README.md`。不得整目录打包 `tools/voxcpm_service/`，避免误带入 `__pycache__`、`.venv`、模型权重、Torch/CUDA wheel、Hugging Face/ModelScope 下载缓存或其它机器相关产物。应用内后台安装默认使用用户设置的 `voxcpm_install_root` 和 `voxcpm_model_cache_root`，并按 `voxcpm_use_model_mirror` 决定是否传递 `UseHfMirror`。应用启动时不自动安装或启动 VoxCPM；用户不勾选安装器 VoxCPM 选项且不点击设置页后台安装/更新时，不得下载模型、创建 venv、安装 Torch、启动服务或写入模型缓存。VoxCPM 安装脚本执行“更新”时必须刷新已安装的 service 文件，并校验复制后的服务包含 `/synthesize_stream`，避免旧 `service.server` 残留导致客户端回退完整 WAV。

## 运行时验证

以下行为不能只凭单元测试声明完成：

- 托盘可用。
- 全局热键可用。
- 弹窗位置和布局可见。
- TTS 可用。
- 打包后的 exe 可启动。

涉及这些区域时，完成报告必须说明实际检查内容；未执行时必须明确列出跳过项和原因。

## FSRS/SQLite 打包注意

项目依赖 `fsrs>=6,<7` 后，打包验证必须确认：

- 依赖被 PyInstaller 收集。
- 首次启动能创建 `storage/oh_my_word.sqlite3`。
- 旧 `learning_state.json` 不被删除。
- portable 包和安装器 payload 不包含本机 `storage/`。
- 包内 `_internal/data/` 数据目录和 exe 同级 `storage/` 写入路径不会混淆。
