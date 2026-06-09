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

### 5. 不自动提交

除非用户明确要求 staging、commit、push 或创建 PR，否则未来 agent 应保持变更未暂存、未提交。

### 6. 安装包使用轻量 WinForms 安装器

- 不引入 Inno Setup 或 NSIS，当前安装器由 `build/build_installer.ps1` 生成 C# WinForms 程序并用系统 `csc.exe` 编译。
- 安装器必须允许用户选择安装目录，并提供桌面快捷方式、开始菜单快捷方式和安装后启动选项。
- 安装器和 portable payload 不打包本机 `storage/` 用户数据。
- 覆盖安装和卸载依赖 `install_manifest.txt` 管理应用文件，不应递归清空用户选择的已有目录。
- PyInstaller one-folder 下内置词库从 `_internal/data/wordbooks/` 读取，运行期 `storage/` 写到 `oh-my-word-py.exe` 同级目录。
