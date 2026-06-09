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

打包载荷只包含应用代码、依赖和 `data/` 内置词库，不得把本机 `storage/` 运行期用户数据打进 portable 包或安装器 payload。PyInstaller one-folder 构建中，内置词库可以位于 `_internal/data/wordbooks/`；运行期 `storage/` 必须位于 `oh-my-word-py.exe` 同级目录。首次启动负责创建缺失的运行期存储文件。

`build/` 可能包含脚本和生成中间物。添加安装器文件前必须确认是否应跟踪，避免误提交大型或机器相关产物。

当前安装包构建命令：

```powershell
.\build\build_installer.ps1
```

安装包输出为 `dist/oh-my-word-setup.exe`。安装器由 build 脚本生成 C# WinForms 程序并用系统 `csc.exe` 编译，必须允许用户选择安装目录，并提供桌面快捷方式、开始菜单快捷方式和安装完成后启动应用的选项。

安装器不得在用户选择的目录已存在时递归删除整个目录。覆盖安装应只删除上一次安装清单记录的应用文件，再写入新 payload。卸载脚本也应只删除安装清单中的应用文件、安装器创建的快捷方式，以及已经变空的应用目录。

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
