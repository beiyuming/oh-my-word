# App Controller 契约

## 范围

本 spec 约束 `main.py` 和 `app/controller.py` 的应用协调职责。它定义启动顺序、模块接线、调度动作分发、当前单词生命周期和退出清理。

## 当前实现

- `main.py` 创建 `QApplication`，关闭最后窗口不退出应用，然后创建并初始化 `AppController`。
- `AppController.initialize()` 负责创建运行目录、logger、设置存储、学习状态存储、活动监控、词库、弹窗、托盘、全局热键、TTS 和 Qt 调度器。
- 首次启动或系统托盘不可用时，controller 打开设置窗口。
- controller 是唯一协调层：弹窗、托盘、热键只发出用户意图，学习状态修改由 controller 接管。
- `current_word` 表示当前可见或刚被操作的词。关闭活动弹窗时必须同步清空它。

## 调度动作

controller 接收 `SchedulerAction`：

- `SHOW_WORD`：如果没有活动弹窗，直接展示；如果已有活动弹窗且是手动触发，关闭旧弹窗后展示；如果已有活动弹窗且是自动触发，将词放入调度队列。
- `REQUEST_FRESH_WORD`：调用选词逻辑获取新词；没有可用词时按返回原因暂停或提示。

手动触发必须优先响应用户，不应被已有自动弹窗阻塞。

## 弹窗动作

当前弹窗支持以下动作：

- 朗读：调用 TTS，成功后记录 `last_pronounced_at`。
- 展开详情：切换可见弹窗详情，记录 `last_expanded_at`。
- 标记掌握：记录 mastered 并关闭弹窗。
- 认识/不认识：记录复习结果并关闭弹窗。
- 稍后：关闭当前弹窗，并通过学习存储层记录当前词的 `snoozed_until`。
- 关闭：关闭当前弹窗。

当前托盘支持：

- `暂停 30 分钟`：由托盘入口触发，写入全局暂停状态并关闭活动弹窗。

## 设置变更

保存设置后必须立即应用：

- 更新托盘启停状态和显示模式。
- 重新绑定全局热键。
- 更新 TTS 口音。
- 根据 enabled 状态启动或暂停调度器；暂停时关闭活动弹窗。

## FSRS/SQLite 边界

controller 不应直接处理 SQLite SQL 或第三方 FSRS 类型。它只调用稳定 repository/service 方法，例如：

- 选择下一个词。
- 记录单词已展示、已朗读、已展开。
- 记录认识/不认识复习。
- 记录当前词稍后。
- 记录全局暂停。

## 验证

- controller 逻辑变更至少运行相关 controller 测试。
- 涉及托盘、弹窗、热键或 TTS 的可见行为时，除单元测试外还要做 Windows 运行时检查。
