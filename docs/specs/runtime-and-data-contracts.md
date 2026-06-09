# 运行与数据契约

## 范围

本 spec 定义 Python 桌面应用在运行、测试、打包和安全修改运行期数据时必须遵守的实现契约。

更具体的模块契约见 `docs/specs/` 下的模块 spec。当前文件保留跨模块运行和验证 guardrails。

## 运行契约

- Python 目标版本：Python 3.11。
- UI 框架：PySide6。
- 主要平台：Windows。
- 源码入口：`main.py`。
- 默认安装命令：`py -3.11 -m pip install -r requirements.txt`。
- 源码运行命令：`py -3.11 main.py`。
- 完整测试命令：`py -3.11 -m pytest tests -q`。
- 打包命令：`.\build\build_exe.ps1`。

除非已经在 Windows 上实际启动应用或构建产物并记录观察结果，否则不要声称应用、托盘、全局热键、弹窗或打包行为已经验证。

## 存储契约

运行期存储位于 `storage/`。源码运行时该目录位于项目根目录；portable 或安装版运行时该目录位于 `oh-my-word-py.exe` 同级目录：

- `settings.json`：仅保存用户配置。
- `oh_my_word.sqlite3`：保存卡片学习状态、近期词、FSRS 载荷、复习日志、稍后状态和全局暂停状态。
- `learning_state.json`：旧版学习状态文件；如果存在，启动时兼容导入到 SQLite，不删除。
- `app.log`：运行日志输出。

FSRS + SQLite 学习存储契约见 `settings-and-storage.md` 和 `study-scheduling.md`。

规则：

- 不要为了让测试通过而删除或覆盖用户存储。
- 测试应使用临时路径或 fixture，不应使用已跟踪/运行期存储。
- 如果存储 schema 改变，必须在同一个检查点更新设置/状态规范化、测试、README/docs 和本 spec。
- 损坏或缺失的运行期 JSON 应通过应用的规范化/回退路径处理，不要靠手动清理用户文件解决。

## 词库契约

内置和导入词库位于 `data/wordbooks/`。

除非更窄的 spec 覆盖，README 中的规则保持权威：

- 按文件名顺序加载 `data/wordbooks/` 下所有 JSON 文件。
- 后加载文件覆盖更早文件中的重复单词。
- 损坏的 JSON 文件被跳过并写入日志。
- 如果没有可用词库，重新创建默认 `kaoyan_core.json`。
- 导入的 JSON/CSV 必须规范化为应用本地词库形状。
- 推荐外部词库下载必须保留来源、许可证和本地目标说明。

不要在未确认跟踪意图前加入大型生成/导入词库。

## UI 与热键契约

- 卡片和弹幕弹窗是 PySide widget。除非协调职责属于 `AppController`，否则行为应尽量局部保留在 overlay 模块内。
- 全局热键是 Windows 原生行为。单元测试可以验证注册/分发逻辑，但真实全局热键完成声明需要 Windows 运行时检查。
- 弹窗几何和布局变化应尽可能有测试；影响用户可见布局时，还需要视觉/运行时检查。
- 不要仅凭测试声称“无重叠”、“可见”、“托盘可用”或“打包应用可用”。

## 打包契约

- PyInstaller 打包由 `oh-my-word-py.spec` 和 `.\build\build_exe.ps1` 驱动。
- portable 包和安装器 payload 不得包含本机 `storage/` 用户运行数据。
- `dist/` 是生成输出。
- `build/` 可能包含脚本和生成中间物；编辑前先检查，因为当前工作区可能已有未跟踪安装器工作。
- 打包变更至少需要完整测试套件和一次 package build。如果预期从构建包运行应用，还要启动构建出的可执行文件并记录检查结果。

## 验证矩阵

| 变更类型 | 最小验证 |
| --- | --- |
| 纯文档/约束 | 阅读路径/链接检查，并自查是否有虚假实现声明 |
| 设置/存储 schema | 针对性 settings/state 测试，加完整 `py -3.11 -m pytest tests -q` |
| SQLite schema/迁移 | 针对性 study store 迁移测试，加完整 `py -3.11 -m pytest tests -q` |
| 词库解析/导入 | 覆盖合法、重复、损坏和导入形状的词库测试 |
| 调度器/复习逻辑 | 覆盖合法迁移和边界时间的单元测试 |
| 弹窗几何/布局 | 针对性 overlay/controller 测试，加 Windows 视觉/运行时检查 |
| 托盘/全局热键 | 针对性逻辑测试，加 Windows 运行时检查 |
| 打包/安装器 | 完整测试套件、PyInstaller 构建，并在可行时启动包检查 |

如果无法执行完整验证路径，汇报被跳过的具体命令或检查以及原因。
