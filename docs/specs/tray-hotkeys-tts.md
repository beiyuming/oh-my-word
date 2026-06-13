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

`PronunciationService` 暴露初始化状态：

- `not_initialized`
- `initializing`
- `ready`
- `unavailable`

`system_qt` provider 采用延迟 warm-up：服务对象应轻量创建，`QTimer.singleShot` 在 Qt 事件循环启动后再触发 `warm_up()`。`warm_up()` 必须幂等，且不应把 `QTextToSpeech` 放进后台线程。

`voxcpm_local` 只允许本地 HTTP endpoint，例如 `127.0.0.1`、`localhost` 或 `::1`，不支持远程服务、云端部署、凭据或 provider token。VoxCPM companion process 失败、未启动、超时或返回空音频时，`speak()` 必须返回 `False` 并记录/上报错误，不得自动回退后又声称 VoxCPM 朗读成功。

`voxcpm_local` 不应把模型加载、网络下载或 companion process 启动放进主进程启动路径；它应保持为轻量 HTTP 适配层。VoxCPM HTTP provider 默认优先调用 `POST {endpoint}/synthesize_stream`，请求体包含 `text`、`accent` 和 `format: "wav"`；服务端使用 VoxCPM `generate_streaming()` 输出 `s16le` PCM chunk，并通过响应头提供 sample rate、channels 和 sample format；桌面端用 `QAudioSink` 边接收边播放。如果旧服务返回 404/405，客户端可以回退到 `POST {endpoint}/synthesize` 的完整 WAV 路径。

使用 `voxcpm_local` 时，controller 应在送入 VoxCPM HTTP provider 前应用 VoxCPM 专用文本格式：独立单词和 `word_and_example` 中的单词部分使用双引号包装为 `"word".`，以强化短词边界；`word_and_example` 中单词和例句之间使用单个空格，不使用双换行强停顿；`example` 模式不应把整句包进引号。如果 `voxcpm_voice_prompt` 非空，应用应按 VoxCPM Voice Design 约定把规范化后的自然语言提示词作为 `(prompt)` 前缀加到合成文本前。该格式化只属于 VoxCPM 路径，`system_qt` 应继续使用普通 `pronunciation_text()` 输出。

VoxCPM service 调用 `generate()` 和 `generate_streaming()` 时必须显式启用官方 badcase 重试参数，降低生成音频异常过短导致的首尾漏读：`retry_badcase=True`、`retry_badcase_max_times=3`、`retry_badcase_ratio_threshold` 默认 `4.0`。默认 `cfg_value` 为 `1.5`，并允许通过 `VOXCPM_CFG_VALUE` 环境变量调整；badcase ratio threshold 允许通过 `VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD` 调整。完整 WAV 和流式 PCM 都必须添加短首尾静音垫，避免短词起音或尾音在本机音频输出中被截断。

完整 WAV fallback 成功时播放返回的 WAV bytes。运行期音频缓存应使用有限文件，例如 `storage/tts_cache/voxcpm-0.wav` 到 `voxcpm-3.wav` 的轮换，不要无界缓存每次生成结果。连续朗读时应先停止旧播放，再写入下一个轮换文件并播放，避免 QtMultimedia 对同一路径 source 复用导致偶发无声。流式 PCM 播放应按 `voxcpm_stream_prebuffer_seconds` 先预缓冲一小段音频再启动 `QAudioSink`，用少量首响延迟换取更低的句中 underflow 卡顿概率；该值在设置页保存后应通过重建 VoxCPM TTS 后端立即作用于后续朗读。

VoxCPM service lifecycle 由 controller 和 `app/voxcpm_service.py` 管理，不属于 `app/tts.py` 的职责。设置页可以后台安装/更新、启动、停止、检测和打开日志；这些操作不能阻塞主 UI。停止服务必须停止本应用当前跟踪的 service process；如果服务是前一次应用会话或安装脚本启动的旧进程，则可以停止同一 endpoint 上命令行可识别为 `uvicorn service.server:app` 的本地 VoxCPM 进程，但不得误杀无关端口进程。`voxcpm_auto_start` 只表示“使用时自动启动”：当用户已选择 `voxcpm_local`、已安装本地服务且打开该开关时，朗读触发前可以启动已安装的本地服务。若未安装，controller 必须提示用户去设置页后台安装，不静默下载数 GB 模型。应用启动时默认不启动 VoxCPM，避免无意占用 GPU/内存。

`system_qt` 在 `warm_up()` 前必须保持 `not_initialized`；warm_up 失败后进入 `unavailable` 并记录错误。`speak()` 在未就绪时必须返回 `False`，controller 不应等待初始化完成再继续 UI 交互。

朗读按钮和默认朗读热键应按 `pronunciation_content_mode` 生成文本：`word` 只读单词，`example` 只读英文例句且缺例句时回退到单词，`word_and_example` 读单词加英文例句并在两者之间使用明确停顿：`word.\n\nexample_sentence`。默认值为 `word_and_example`。如果词条没有有效英文例句，则只朗读单词。不要把 `example_translation` 送入英语 TTS。

朗读成功后，controller 记录当前词 `last_pronounced_at`。静音设置开启时不朗读。

当用户触发朗读时，如果 TTS 仍在初始化，应通过托盘提示“语音正在初始化，请稍后”；如果已 `unavailable` 或朗读失败，应提示失败原因。相同初始化阶段的提示要节流，避免同一状态下重复刷屏。

## 验证

- 热键解析和注册分发可用单元测试覆盖。
- 真实全局热键和托盘消息必须在 Windows 运行时检查。
- `system_qt` 后端可用性依赖系统语音环境；无法验证时必须明确说明。
- `voxcpm_local` 必须分别验证 service-down 失败路径、本地 service 运行时的流式 PCM 路径和完整 WAV fallback 路径；没有安装 VoxCPM service-only 依赖时，必须将真实合成播放列为未验证项。
