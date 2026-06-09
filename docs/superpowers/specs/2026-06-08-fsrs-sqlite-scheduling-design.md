# FSRS 与 SQLite 调度设计

## 稳定文档归属

本文是 2026-06-08 的 dated 设计草案，用于记录 FSRS + SQLite 需求讨论和设计来源。长期项目结构参考应优先阅读：

- `docs/architecture/module-boundaries.md`
- `docs/specs/settings-and-storage.md`
- `docs/specs/study-scheduling.md`
- `docs/specs/popup-overlays.md`

如果本文与稳定模块 spec 冲突，优先以 `docs/specs/` 中的模块契约为准；当前实现事实仍以源码和测试为准。

## 目标

在保持 `oh my word` 轻量托盘弹词体验的前提下，将学习状态从全量 JSON 文件迁移到 SQLite，并用 FSRS 间隔重复算法管理单词卡片的记忆状态。实现后，应用仍以卡片或弹幕轻量弹出单词，但底层可以支撑更大的词库、更长的复习历史和后续统计能力。

## 范围

- 保留 `settings.json` 作为用户设置存储。
- 新增 `storage/oh_my_word.sqlite3` 保存卡片学习状态、复习日志、短期稍后状态和必要的词条索引。
- 启动时从旧 `storage/learning_state.json` 做一次性兼容导入；导入后不删除旧文件。
- 使用 FSRS 管理 `stability`、`difficulty`、`due_at` 等记忆字段。
- 保持两按钮轻量评分：`认识` 映射到 FSRS `Good`，`不认识` 映射到 FSRS `Again`。
- 新增“稍后”语义：当前词稍后再问，不更新 FSRS，不写正式复习日志。
- 支持全局“暂停一段时间”语义，用于工作忙时暂时停止弹词。
- 保持现有托盘、弹窗、热键和显示模式的产品形态。

不在本次范围内：

- 完整复制 Anki 的 note/model/deck/sync 数据模型。
- 做 FSRS 参数优化器或跨设备同步。
- 把所有应用设置迁入数据库。
- 做复杂卡片模板、正反卡或填空卡。
- 默认展示四档评分 UI；四档评分可以作为未来可选模式。

## 产品语义

### 轻量评分

弹窗默认保留轻量选择：

- `认识`：用户完成一次成功复习，映射到 FSRS `Good`。
- `不认识`：用户完成一次失败复习，映射到 FSRS `Again`。
- `稍后`：用户暂时不方便判断记忆，不更新 FSRS。
- `关闭`：关闭当前弹窗，不记录复习结果。

`Hard` 和 `Easy` 不在默认 UI 中出现。未来如果需要更高精度，可以增加设置项切换到四档评分。

### 稍后

“稍后”是调度层行为，不是记忆评分。

- 对当前卡片写入 `snoozed_until = now + 默认稍后时长`。
- 不修改 `stability`、`difficulty`、`due_at`、`reps`、`lapses`。
- 不写入正式 `review_log`。
- 稍后时长默认 30 分钟，可通过设置页配置。

### 全局暂停

全局暂停用于用户工作忙时暂时停止所有弹词。

- 存储 `app_snoozed_until`。
- 调度器发现当前时间早于 `app_snoozed_until` 时不弹任何单词。
- 全局暂停不改变任何卡片的 FSRS 状态。

## 架构

现有 `SchedulerCore` 和 `QtScheduler` 继续负责“桌面何时打扰用户”：最短/最长间隔、用户活动频率和手动触发。新增数据库存储层负责“应该展示哪个卡片”和“复习后如何更新记忆状态”。

边界如下：

- `AppController`：继续协调托盘、弹窗、热键、TTS 和调度器。
- `SchedulerCore`：保留轻量打扰节奏，不直接实现 FSRS。
- `StudyRepository`：新增 SQLite repository，提供卡片查询、复习更新、稍后、全局暂停和旧 JSON 导入。
- `FsrsReviewService`：新增 FSRS 适配层，隔离第三方库类型和本项目 `WordProgress`/card 数据。
- `words.py`：继续负责词库加载、导入和规范化；第一版不要求词库完全迁入数据库。

这样可以避免把 FSRS 到期时间误用为桌面弹窗频率。FSRS 决定记忆优先级，现有调度器决定弹窗打扰节奏。

## 数据契约

### 数据库文件

数据库路径为：

```text
storage/oh_my_word.sqlite3
```

数据库必须使用 SQLite 标准库 `sqlite3`，除 FSRS 算法库外不引入重量级 ORM。

### 表结构

`schema_migrations` 记录已应用迁移：

```sql
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

`cards` 保存每个单词的调度状态：

```sql
CREATE TABLE cards (
  id INTEGER PRIMARY KEY,
  word TEXT NOT NULL UNIQUE,
  due_at TEXT,
  state TEXT NOT NULL DEFAULT 'new',
  stability REAL,
  difficulty REAL,
  reps INTEGER NOT NULL DEFAULT 0,
  lapses INTEGER NOT NULL DEFAULT 0,
  mastered INTEGER NOT NULL DEFAULT 0,
  suspended INTEGER NOT NULL DEFAULT 0,
  snoozed_until TEXT,
  last_shown_at TEXT,
  last_pronounced_at TEXT,
  last_expanded_at TEXT,
  last_reviewed_at TEXT,
  last_rating TEXT,
  show_count INTEGER NOT NULL DEFAULT 0,
  known_count INTEGER NOT NULL DEFAULT 0,
  unknown_count INTEGER NOT NULL DEFAULT 0,
  fsrs_payload_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`recent_words` 保存轻量近期去重窗口：

```sql
CREATE TABLE recent_words (
  id INTEGER PRIMARY KEY,
  word TEXT NOT NULL,
  shown_at TEXT NOT NULL
);
```

`review_log` 保存正式复习记录：

```sql
CREATE TABLE review_log (
  id INTEGER PRIMARY KEY,
  card_id INTEGER NOT NULL,
  word TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  rating TEXT NOT NULL,
  state_before TEXT,
  state_after TEXT,
  scheduled_days INTEGER,
  elapsed_days INTEGER,
  duration_ms INTEGER,
  fsrs_review_log_json TEXT,
  FOREIGN KEY(card_id) REFERENCES cards(id)
);
```

`app_state` 保存全局运行状态：

```sql
CREATE TABLE app_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

第一版不需要把完整词条内容写入 SQLite。词条内容仍来自 `data/wordbooks/` 的 JSON 词库，`cards.word` 作为学习状态键。

### 索引

必须创建以下索引：

```sql
CREATE INDEX idx_cards_due ON cards(due_at);
CREATE INDEX idx_cards_snoozed ON cards(snoozed_until);
CREATE INDEX idx_cards_flags ON cards(mastered, suspended);
CREATE INDEX idx_recent_words_shown_at ON recent_words(shown_at);
CREATE INDEX idx_review_log_word_time ON review_log(word, reviewed_at);
```

## 选词契约

候选卡片必须满足：

- `mastered = 0`
- `suspended = 0`
- `snoozed_until IS NULL OR snoozed_until <= now`
- 如果全局 `app_snoozed_until > now`，不返回任何候选

优先级：

1. 到期卡片：`due_at IS NOT NULL AND due_at <= now`
2. 新卡片：词库中存在但数据库中没有卡片，或卡片 `state = 'new'`
3. 未掌握旧卡片：没有到期但仍可学习的卡片

在同一优先级内应避开最近展示的单词；如果近期窗口耗尽候选，可以回退到该优先级原始候选池。

当所有词都 `mastered = 1` 或没有可学习候选时，返回与当前 `WordSelectionResult` 兼容的暂停信号。

## 复习契约

正式复习只由 `认识` 和 `不认识` 触发：

- `认识` 调用 FSRS `Good`。
- `不认识` 调用 FSRS `Again`。
- 更新 `cards` 中的 `due_at`、`state`、`stability`、`difficulty`、`reps`、`lapses`、`last_reviewed_at`、`last_rating`。
- 写入一条 `review_log`。

非正式动作：

- `稍后` 只更新 `snoozed_until`。
- `关闭` 不更新 FSRS，不写 `review_log`。
- `标记掌握` 只设置 `mastered = 1`，不写 FSRS 复习日志。
- `朗读` 只更新 `last_pronounced_at`。
- `展开详情` 只更新 `last_expanded_at`。

## 迁移契约

启动时如果存在旧 `storage/learning_state.json`：

- 数据库不存在或未标记完成导入时，读取旧 JSON。
- 为每个 `progress` 条目创建或更新 `cards` 行。
- 保留 `show_count`、`last_*`、`due_at`、`review_count`、`known_count`、`unknown_count`、`stability`、`difficulty`、`last_rating`、`mastered`。
- 将旧 `recent_words` 写入 `recent_words`。
- 在 `app_state` 写入 `legacy_learning_state_imported_at`。
- 不删除、不覆盖旧 JSON 文件。

旧 JSON 格式损坏时，记录 warning 并继续使用空数据库状态，不阻塞应用启动。

## 依赖契约

`requirements.txt` 增加 FSRS Python 包，版本约束使用：

```text
fsrs>=6,<7
```

代码不得直接在 controller 中散落第三方 FSRS 类型。第三方类型只允许出现在 `FsrsReviewService` 或其测试中。

## 测试

必须添加或更新以下测试：

- SQLite schema 初始化和幂等迁移。
- 旧 `learning_state.json` 到 SQLite 的兼容导入。
- 到期卡片、新卡片、近期词避让、全局暂停和单词稍后过滤。
- `认识` 写入 FSRS 更新结果和 `review_log`。
- `不认识` 写入 FSRS 更新结果和 `review_log`。
- `稍后` 不改变 FSRS 字段、不写 `review_log`。
- `关闭` 不写复习结果。
- controller 在新 repository 接口下仍能展示、朗读、展开、掌握和复习当前词。

完整验证命令：

```powershell
py -3.11 -m pytest tests -q
```

如果改动影响弹窗按钮、托盘菜单、全局热键或打包行为，还必须做 Windows 运行时检查；不能只依赖测试声明完成。

## 风险

- FSRS 包 API 可能随版本变化，必须用适配层隔离。
- 迁移必须保护用户已有 `storage/learning_state.json`，不能删除或重写。
- SQLite 写入要避免每个小动作全库扫描。
- 词库仍来自 JSON，数据库卡片状态和词库内容需要用 `word` 稳定关联。
- “稍后”和“关闭”不能被误记为复习，否则会污染 FSRS 记忆状态。
