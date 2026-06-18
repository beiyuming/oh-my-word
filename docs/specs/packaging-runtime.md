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

打包载荷包含应用代码、依赖、`data/` 内置词库，以及供应用内 VoxCPM 运行时/服务逻辑使用的 `tools/voxcpm_service` service-only 文件。不得把本机 `storage/` 运行期用户数据打进 portable 包或安装器 payload。PyInstaller one-folder 构建中，内置词库可以位于 `_internal/data/wordbooks/`，VoxCPM service-only 文件可以位于 `_internal/tools/voxcpm_service/`；运行期 `storage/` 必须位于 `oh-my-word-py.exe` 同级目录。首次启动负责创建缺失的运行期存储文件。

`build/` 可能包含脚本和生成中间物。添加安装器文件前必须确认是否应跟踪，避免误提交大型或机器相关产物。

当前安装包构建命令：

```powershell
.\build\build_installer.ps1
```

安装包默认输出为带版本号的文件名，例如 `dist/oh-my-word-setup-v0.1.10.exe`。版本号必须来自代码内单一版本源，并同步显示在安装器窗口标题/主标题和设置页关于/更新日志中；后续每次重新打包发布都必须递增或明确维护版本号和更新日志。安装器由 build 脚本生成 C# WinForms 程序并用系统 `csc.exe` 编译，必须允许用户选择安装目录，并提供桌面快捷方式、开始菜单快捷方式和安装完成后启动应用的选项。

当产品采用预构建 VoxCPM2 运行时时，主应用安装器与 runtime package/运行时包分开发布：GitHub Release 负责主安装器与说明文件，ModelScope 负责与环境矩阵绑定的运行时包、模型包和对应 checksum 文件，例如 `voxcpm2-runtime-win-x64-cu130-r1.zip` 与 `voxcpm2-model-cu130-r1.zip`。主应用安装器负责桌面应用本体，运行时包与模型包负责 Windows 10/11 x64 + NVIDIA GPU 的受支持 VoxCPM2 本地运行时矩阵。

每次“更新并重新打包安装包”完成后，发布流程必须执行一次 Git 提交、推送到 GitHub、创建同版本 tag，并创建 GitHub Release。提交前必须完成对应验证，并只暂存本次发布相关的源码、测试、文档、版本号、更新日志和打包脚本；不得因工作区已有 dirty 状态而把无关文件带入提交。生成的 `dist/` 安装包和 portable payload 默认仍是构建产物，不进入 Git 提交；只有用户明确要求跟踪某个发布产物时才可以暂存。提交信息应包含版本号，例如 `release: v0.1.10`；tag 应使用同一版本号，例如 `v0.1.10`。

安装包二进制必须随同版本 GitHub Release 发布，而不是依赖普通 `git push`。发布提交、branch push 和 tag push 成功后，应创建或更新同版本 Release，并上传带版本号的安装包附件，例如 `dist/oh-my-word-setup-v0.1.10.exe`。如果 `gh` 未安装/未登录、token 缺失、网络或权限导致 Release 附件上传失败，完成报告必须说明失败原因、已推送的 commit/branch/tag 状态、安装包本地路径，并给出可手动执行的 `gh release create` 或 `gh release upload --clobber` 命令。

安装器不得在用户选择的目录已存在时递归删除整个目录。覆盖安装应先检查运行中的旧应用；如果目标安装目录的 `oh-my-word-py.exe` 仍在运行，安装器必须提示用户关闭应用后重试，不应继续删除清单文件并暴露 DLL 占用导致的底层权限异常。覆盖安装应只删除上一次安装清单记录的应用文件，再写入新 payload。卸载脚本也应只删除安装清单中的应用文件、安装器创建的快捷方式，以及已经变空的应用目录。

安装器不再提供 `Install local VoxCPM pronunciation engine`、镜像开关、模型目录选择或任何脚本式 VoxCPM setup UI。主安装器只负责主程序文件、快捷方式和卸载脚本；VoxCPM2 的运行时和模型统一在应用设置页内通过 ModelScope 下载或手动导入完成。

安装后的主应用还必须能从设置页优先下载并导入 ModelScope 上的 VoxCPM2 运行时包和模型包，因此 portable payload 中的 VoxCPM 文件只能包含轻量 service-only 文件：`install_local.ps1`、`server.py`、`engine.py`、`requirements.txt`、`README.md`。不得整目录打包 `tools/voxcpm_service/`，避免误带入 `__pycache__`、`.venv`、模型权重、Torch/CUDA wheel、Hugging Face/ModelScope 下载缓存或其它机器相关产物。应用内应支持四条路径：`下载并导入运行时包`、`下载并导入模型包`、`导入运行时包`、`导入模型包`。运行时导入时，运行时仍落位到用户设置的 `voxcpm_install_root`；模型包导入时，模型落位到用户设置的 `voxcpm_model_cache_root`。应用启动时不自动安装或启动 VoxCPM；用户不点击设置页下载/导入运行时包或模型包时，不得下载模型、创建 venv、安装 Torch、启动服务或写入模型缓存。

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
