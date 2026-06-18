# 设置与存储契约

## 范围

本 spec 约束 `app/settings.py`、`app/settings_window.py`、运行期 `storage/` 文件，以及 `app/study_store.py` 的 SQLite 存储层。它是设置 schema、学习状态迁移和运行期数据保护的稳定来源。

## 当前运行期文件

- `storage/settings.json`：仅保存用户配置。
- `storage/oh_my_word.sqlite3`：保存卡片学习状态、近期词、FSRS 载荷、复习日志、稍后状态和全局暂停状态。
- `storage/learning_state.json`：旧版学习状态文件；如果存在，启动时兼容导入，不删除。
- `storage/app.log`：运行日志。

规则：

- 不要为了测试或迁移方便删除用户运行期文件。
- 测试必须使用临时路径或 fixture。
- 损坏 JSON 应走规范化回退路径并记录 warning，不应要求用户手动清理。

## 当前设置字段

`AppSettings` 当前保存：

- 启停状态和显示模式。
- 卡片/弹幕位置。
- 最小/最大弹出间隔。
- 用户活动阈值和延迟权重。
- 卡片停留时长。
- 稍后时长，默认 30 分钟。
- 弹窗自动朗读：`auto_pronounce_on_popup` 默认 `false`。
- 自动朗读延迟：`auto_pronounce_delay_seconds` 默认 `1.0` 秒，规范化范围 `0.00` 到 `10.00` 秒。
- 静音和英/美音偏好。
- 朗读内容：`pronunciation_content_mode` 默认 `word_and_example`，可选 `word`、`example`、`word_and_example`。
- 发音 provider：`tts_provider` 默认 `system_qt`，可选 `voxcpm_local`。
- VoxCPM 本地服务地址：`voxcpm_endpoint` 默认 `http://127.0.0.1:8808`，第一版只允许本地 HTTP endpoint。
- VoxCPM 请求超时：`voxcpm_timeout_seconds` 默认 15 秒，规范化范围为 1 到 120 秒。
- VoxCPM 安装目录：`voxcpm_install_root` 默认随运行目录解析为 `<软件运行目录>\tts\voxcpm`；非运行时静态 fallback 为 `%LOCALAPPDATA%\OhMyWord\tts\voxcpm`。该目录用于保存独立 venv、服务脚本和安装日志。
- VoxCPM 模型缓存目录：`voxcpm_model_cache_root` 默认随运行目录解析为 `<软件运行目录>\tts\voxcpm\models`；非运行时静态 fallback 为 `%LOCALAPPDATA%\OhMyWord\tts\voxcpm\models`。该目录用于保存 VoxCPM2 模型文件并传递给 service-only 安装脚本。
- VoxCPM 模型下载镜像：`voxcpm_use_model_mirror` 默认 `true`，设置页下载运行时包/模型包时优先使用国内镜像 / ModelScope 路径。
- VoxCPM 使用时自动启动：`voxcpm_auto_start` 默认 `false`。只有用户选择 `voxcpm_local` 并打开该开关后，controller 才会在朗读时尝试启动已安装的本地服务。
- VoxCPM 语气提示词：`voxcpm_voice_prompt` 默认空字符串。用户可在设置页输入自然语言 voice design 描述；保存时应规范化为单行短文本，只在 `voxcpm_local` 合成文本前作为 VoxCPM `(prompt)` 前缀使用。
- VoxCPM 流式预缓冲：`voxcpm_stream_prebuffer_seconds` 默认 `0.35` 秒，规范化范围为 `0.00` 到 `2.00` 秒；负数或非数字回退默认值，超过上限夹到 `2.00`。该字段控制流式 PCM 播放启动前先攒多少音频，保存设置后 controller 应重建 TTS 后端，使后续朗读使用新值。
- 朗读、详情、立刻弹出、标记掌握、认识、不认识、关闭快捷键。

设置窗口必须按类别组织：学习、显示、发音、快捷键、词库、关于。自动朗读开关、自动朗读延迟、朗读内容、口音、发音引擎、VoxCPM 安装目录、模型目录、镜像开关、使用时自动启动开关、语气提示词、流式预缓冲、ModelScope 路径字段，以及下载/导入运行时包、下载/导入模型包、启动/停止/检测/打开日志入口属于发音分类。点击发音分类中的 VoxCPM 下载/导入/启动/停止/检测/打开日志入口前，应先读取并应用当前窗口里已编辑但尚未保存的 VoxCPM 路径和镜像设置，避免动作基于过时状态。关于分类必须显示当前应用版本和更新日志；版本来源应来自代码内单一版本源，不应在 UI 中手写另一个版本号。

发音分类应提供 `下载并导入运行时包` 主入口，用于从 ModelScope 拉取预构建 runtime zip 与 model zip 并顺序导入；同时提供 `下载并导入模型包` 用于运行时已就绪后的单独模型恢复；并保留 `导入 VoxCPM 运行时包` 和 `导入模型包` 作为手动下载后的兜底入口。上述入口不新增额外必需字段，但允许暴露可编辑的 ModelScope 命名空间、仓库名、运行时包文件名和最低驱动版本字段，方便后续切换仓库或资产名。设置页状态区必须展示运行时导入状态和只读元信息，例如 runtime ID、CUDA 标签、最低驱动要求和模型版本。

字段新增时必须同步：

- `AppSettings` 默认值。
- `normalize_settings()`。
- `settings_to_dict()`。
- 设置窗口读写。
- 单元测试。
- README 或相关 stable spec。

## SQLite 学习存储

学习状态位于：

```text
storage/oh_my_word.sqlite3
```

`settings.json` 继续保存设置，不迁入数据库。

SQLite 表：

- `schema_migrations`：迁移版本和应用时间。
- `cards`：每个单词的学习/调度状态。
- `recent_words`：近期展示窗口。
- `review_log`：正式复习日志。
- `app_state`：全局暂停等运行状态。

`cards` 必须包含以下稳定字段：

- `word`
- `due_at`
- `state`
- `stability`
- `difficulty`
- `reps`
- `lapses`
- `mastered`
- `suspended`
- `snoozed_until`
- `last_shown_at`
- `last_pronounced_at`
- `last_expanded_at`
- `last_reviewed_at`
- `last_rating`
- `show_count`
- `known_count`
- `unknown_count`
- `fsrs_payload_json`
- `created_at`
- `updated_at`

必须创建索引覆盖 due 查询、snooze 查询、mastered/suspended 过滤、近期展示排序和 review log 按词查询。

## 旧 JSON 迁移

启动时如果存在旧 `storage/learning_state.json`：

- 数据库未标记已导入时，读取旧 JSON。
- 使用现有学习状态规范化逻辑解析。
- 将每个 `progress` 条目导入 `cards`。
- 将旧 `recent_words` 导入 `recent_words`。
- 写入 `app_state.legacy_learning_state_imported_at`。
- 不删除、不覆盖旧 JSON。

旧 JSON 损坏时记录 warning，继续使用空数据库状态。

## 验证

- 设置 schema 变更运行 settings 测试和完整测试。
- SQLite schema 或迁移变更必须有幂等初始化测试和旧 JSON 导入测试。
- 运行期数据迁移不能在真实 `storage/` 上做破坏性验证。
