# Specs 总览

## 目的

`docs/specs/` 保存实现层契约，供 agent 编码和验证时遵循。这些文件应足够具体，能够支撑测试、运行检查或验收标准。

## 当前 Specs

- `runtime-and-data-contracts.md`：Python/PySide 运行命令、存储和词库契约、弹窗/热键验证要求，以及打包规则。
- `app-controller.md`：`main.py` 和 `app/controller.py` 的应用协调契约。
- `settings-and-storage.md`：设置 schema、运行期存储、SQLite 学习状态和旧 JSON 迁移契约。
- `study-scheduling.md`：桌面调度、复习算法、FSRS 调度、稍后和全局暂停契约。
- `wordbook-catalog.md`：词库加载、导入、下载、重复词合并和词条规范化契约。
- `popup-overlays.md`：卡片/弹幕弹窗、定位、按钮、信号和视觉验证契约。
- `tray-hotkeys-tts.md`：托盘菜单、全局热键和离线发音契约。
- `packaging-runtime.md`：源码运行、测试、PyInstaller、安装器和运行时验证契约。

## 归属规则

- 持久契约放在 specs：字段、状态、数据形状、命令、验证要求和跨模块行为。
- 稳定叙事上下文和阅读路径放在 `docs/00-overview.md`。
- 当前状态、近期决策、风险和交接放在 `memory/`。
- 精确当前行为由源码和测试负责。
- 当前符号、调用者、被调用者和影响半径由 CodeGraph 负责。
- 模块分组和 spec 映射由 `docs/architecture/module-boundaries.md` 负责。
- `docs/superpowers/` 下 dated specs/plans 是历史上下文和执行计划，不是稳定模块契约。

## 新增 Spec 的条件

当任务改变未来 agent 必须遵守的契约时，新增聚焦 spec，例如：

- 调度器/复习状态迁移
- 弹窗几何和交互状态
- 词库导入/导出数据映射
- 安装包/打包布局
- 设置 schema 迁移

每个 spec 应包含：

1. 范围和归属方。
2. 数据或状态契约。
3. 允许行为和禁止行为。
4. 验证命令或运行时检查。
5. 已知占位或部分验证事项。

## 模块映射

| 修改区域 | 优先阅读 |
| --- | --- |
| `main.py`, `app/controller.py` | `app-controller.md` |
| `app/settings.py`, `app/settings_window.py`, `app/study_store.py` | `settings-and-storage.md` |
| `app/scheduler.py`, `app/review.py`, `app/fsrs_service.py` | `study-scheduling.md` |
| `app/words.py`, `data/wordbooks/` | `wordbook-catalog.md` |
| `app/overlays/*` | `popup-overlays.md` |
| `app/tray.py`, `app/hotkeys.py`, `app/tts.py` | `tray-hotkeys-tts.md` |
| `build/`, `oh-my-word-py.spec`, `requirements.txt` | `packaging-runtime.md` |
