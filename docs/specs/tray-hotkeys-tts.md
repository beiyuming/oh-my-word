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

TTS 由 `PronunciationService` 对 controller 提供统一接口。第一版支持两个 provider：

- `system_qt`：默认 provider，使用 `QtTextToSpeech`，优先选择英语 voice，并根据设置偏好英音或美音。
- `voxcpm_local`：可选 provider，通过本地 HTTP endpoint 调用用户本机 companion process，默认 endpoint 为 `http://127.0.0.1:8808`。

`voxcpm_local` 只允许本地 HTTP endpoint，例如 `127.0.0.1`、`localhost` 或 `::1`，不支持远程服务、云端部署、凭据或 provider token。VoxCPM companion process 失败、未启动、超时或返回空音频时，`speak()` 必须返回 `False` 并记录/上报错误，不得自动回退后又声称 VoxCPM 朗读成功。

VoxCPM HTTP provider 调用 `POST {endpoint}/synthesize`，请求体包含 `text`、`accent` 和 `format: "wav"`；成功时播放返回的 WAV bytes。运行期音频缓存应使用有限文件，例如 `storage/tts_cache/voxcpm-current.wav`，不要无界缓存每次生成结果。

`system_qt` 不可用时记录错误，不阻塞应用启动。

朗读按钮和默认朗读热键应朗读当前单词加英文例句：`word. example_sentence`。如果词条没有有效英文例句，则只朗读单词。不要把 `example_translation` 送入英语 TTS。

朗读成功后，controller 记录当前词 `last_pronounced_at`。静音设置开启时不朗读。

## 验证

- 热键解析和注册分发可用单元测试覆盖。
- 真实全局热键和托盘消息必须在 Windows 运行时检查。
- `system_qt` 后端可用性依赖系统语音环境；无法验证时必须明确说明。
- `voxcpm_local` 必须分别验证 service-down 失败路径和本地 service 运行时的 WAV 播放路径；没有安装 VoxCPM service-only 依赖时，必须将真实合成播放列为未验证项。
