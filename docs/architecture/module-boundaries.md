# 模块边界

## 目的

本文件定义项目的稳定模块分组、依赖方向和对应 spec。它用于回答“改某类代码前应该读哪些结构文档”，不替代 CodeGraph 对当前符号和调用关系的查询。

## 模块分组

| 模块组 | 当前代码 | 稳定 spec | 职责 |
| --- | --- | --- | --- |
| 应用协调 | `main.py`, `app/controller.py` | `docs/specs/app-controller.md` | 启动、初始化、调度动作分发、弹窗动作协调、退出 |
| 设置与存储 | `app/settings.py`, `app/settings_window.py`, `app/study_store.py` | `docs/specs/settings-and-storage.md` | 设置 schema、运行期文件、日志、SQLite、旧 JSON 迁移 |
| 学习调度 | `app/scheduler.py`, `app/review.py`, `app/fsrs_service.py` | `docs/specs/study-scheduling.md` | 桌面弹出节奏、复习算法、选词优先级、稍后/暂停语义 |
| 词库目录 | `app/words.py`, `data/wordbooks/` | `docs/specs/wordbook-catalog.md` | 词库加载、导入、下载、重复词合并、词条规范化 |
| 弹窗层 | `app/overlays/card_popup.py`, `app/overlays/barrage_popup.py` | `docs/specs/popup-overlays.md` | 卡片/弹幕 UI、位置、按钮、拖拽、auto-hide、动画 |
| 托盘/热键/发音 | `app/tray.py`, `app/hotkeys.py`, `app/tts.py` | `docs/specs/tray-hotkeys-tts.md` | 托盘菜单、全局热键、离线 TTS |
| 打包运行 | `main.py`, `build/`, `oh-my-word-py.spec` | `docs/specs/packaging-runtime.md` | 源码运行、PyInstaller、安装器、运行时验证 |

## 依赖方向

- `main.py` 只负责创建 `QApplication`、创建 `AppController` 并进入事件循环。
- `AppController` 是协调层，可以依赖设置、词库、调度器、弹窗、托盘、热键和 TTS 模块。
- 弹窗、托盘和热键只表达用户意图，不直接修改学习状态；状态更新由 controller 协调。
- `SchedulerCore` 应保持纯逻辑，`QtScheduler` 只负责把纯调度逻辑接到 `QTimer`。
- `words.py` 负责词库内容和选词输入，不应直接依赖 UI。
- 存储层不应依赖 PySide widget；`StudyStore` 和 `FsrsReviewService` 应保持可单元测试。
- 第三方 FSRS 类型只能出现在 FSRS 适配层及其测试中，不应散落到 controller、弹窗或托盘模块。

## 文档使用规则

- 做跨模块功能前，先读本文件，再读受影响模块的 spec。
- 当前实现事实以源码和测试为准；模块 spec 记录稳定契约和已批准的目标设计。
- dated 文档位于 `docs/superpowers/`，作为需求讨论和实现计划历史；稳定契约应同步到 `docs/specs/`。
- 如果模块边界发生变化，同步更新本文件和相关 spec。
