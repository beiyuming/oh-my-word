# 托盘、热键与发音契约

## 范围

本 spec 约束 `app/tray.py`、`app/hotkeys.py` 和 `app/tts.py`。它定义托盘菜单、全局热键注册和离线发音行为。

## 托盘

托盘当前支持：

- 自动学习启停。
- 立刻弹出一个单词。
- 切换显示方式。
- 打开设置。
- 退出。

托盘 tooltip 应反映学习启停状态和当前显示模式。系统托盘不可用时，controller 必须打开设置窗口作为可见入口。

托盘包含 `暂停 30 分钟` 菜单项。触发后由 controller 写入全局暂停状态并关闭活动弹窗。

## 全局热键

全局热键使用 Windows 原生能力。当前动作：

- `pronounce`
- `toggle_details`
- `trigger_now`
- `mark_mastered`
- `known`
- `unknown`
- `dismiss`

热键注册失败应记录并通过托盘消息提示。设置保存后必须重新绑定热键。

第一版 `稍后` 不新增全局热键，避免热键数量继续膨胀。未来如果增加，必须同步设置 schema、设置 UI、热键注册和 controller 测试。

## 发音

TTS 使用 `QtTextToSpeech`，优先选择英语 voice，并根据设置偏好英音或美音。TTS 不可用时记录错误，不阻塞应用启动。

朗读按钮和默认朗读热键应朗读当前单词加英文例句：`word. example_sentence`。如果词条没有有效英文例句，则只朗读单词。不要把 `example_translation` 送入英语 TTS。

朗读成功后，controller 记录当前词 `last_pronounced_at`。静音设置开启时不朗读。

## 验证

- 热键解析和注册分发可用单元测试覆盖。
- 真实全局热键和托盘消息必须在 Windows 运行时检查。
- TTS 后端可用性依赖系统环境；无法验证时必须明确说明。
