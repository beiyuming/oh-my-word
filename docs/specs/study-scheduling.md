# 学习调度契约

## 范围

本 spec 约束 `app/scheduler.py`、`app/review.py`、`app/fsrs_service.py` 以及学习选词和复习结果语义。它不负责弹窗视觉，也不负责词库格式。

## 当前桌面调度

`SchedulerCore` 负责纯逻辑调度：

- `enabled = false` 时不产生下一次 due 时间。
- 基础延迟在最小/最大分钟之间随机。
- 用户活动频率达到阈值时延长弹出间隔。
- 自动触发到点后发出 `REQUEST_FRESH_WORD` 或队列中的 `SHOW_WORD`。
- 手动触发会绕过下一次 due 时间，优先返回队列词或请求新词。

`QtScheduler` 只负责把纯逻辑接入 `QTimer`。

## 当前选词语义

当前选词从词库和学习状态中选择：

1. 排除 mastered 单词。
2. 优先到期复习词。
3. 其次新词。
4. 再次未掌握旧词。
5. 同一池内避开近期展示词；候选被近期窗口耗尽时允许回退。

全部单词 mastered 时返回暂停信号。

## FSRS 复习语义

- `认识` 映射为 FSRS `Good`。
- `不认识` 映射为 FSRS `Again`。
- 默认 UI 不暴露 `Hard` 和 `Easy`。
- 第三方 FSRS 类型只允许出现在 `FsrsReviewService` 及其测试中。
- controller 和弹窗只使用项目级 rating，例如 `known` / `unknown`。

正式复习必须：

- 更新 card 的 `due_at`、`state`、`stability`、`difficulty`、`reps`、`lapses`、`last_reviewed_at`、`last_rating`。
- 写入 `review_log`。

非正式动作不得污染 FSRS：

- `稍后` 只写 `snoozed_until`。
- `关闭` 不写复习结果。
- `标记掌握` 只写 mastered。
- `朗读` 只写 `last_pronounced_at`。
- `展开详情` 只写 `last_expanded_at`。

## 稍后与全局暂停

`稍后` 是当前词级 snooze：

- 默认 30 分钟，可通过设置页 `稍后时长` 调整。
- 不改变 FSRS 字段。
- 不写 `review_log`。

全局暂停是应用级 snooze：

- 写入 `app_snoozed_until`。
- 暂停期间不选择任何单词。
- 不改变任何卡片的记忆状态。

## 验证

- 调度变更运行 scheduler 测试。
- 复习算法变更运行 review 或 FSRS adapter 测试。
- 选词变更覆盖 due、新词、recent fallback、mastered、snooze 和全局暂停。
- controller 接入变更还需运行 controller 测试。
