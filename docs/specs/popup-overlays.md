# 弹窗层契约

## 范围

本 spec 约束 `app/overlays/card_popup.py` 和 `app/overlays/barrage_popup.py`。它定义卡片/弹幕弹窗的展示、按钮、定位、关闭和信号边界。

## 通用契约

- 弹窗是 PySide widget，不直接修改学习状态。
- 弹窗通过 signal 表达用户意图。
- controller 负责把 signal 转换为学习状态、TTS 或调度动作。
- 弹窗必须支持无需激活主窗口显示，并保持置顶。

## 卡片弹窗

卡片弹窗当前支持：

- 展示单词、IPA、摘要和详情；详情必须包含词条的 `example_sentence` 和 `example_translation`。
- 详情展开/收起。
- 朗读、标记掌握、认识、不认识、关闭。
- 根据设置定位到鼠标附近、右下角、顶部居中、中心或随机位置。
- auto-hide，并在 hover 或拖拽时暂停隐藏。
- 鼠标拖拽移动。

随机位置必须 clamp 到当前屏幕可用几何范围内。

## 弹幕弹窗

弹幕弹窗当前支持：

- 展示单词、IPA、摘要和详情；详情必须包含词条的 `example_sentence` 和 `example_translation`。
- 详情展开时暂停 drift，收起后恢复。
- 朗读、标记掌握、认识、不认识、关闭。
- 从屏幕右侧外进入，并在完整离开左侧边界后关闭。
- 鼠标 hover 暂停，拖拽后从新位置继续。

IPA label 必须在正常内容压力下保持可见空间。

## 稍后按钮

卡片和弹幕都应增加 `稍后` 动作：

- UI 上与 `认识`、`不认识` 同级。
- 触发 signal，不直接写数据库。
- controller 收到后记录当前词 `snoozed_until` 并关闭弹窗。
- 不写正式复习日志。

## 验证

- 几何变更应有单元测试覆盖边界。
- 按钮 signal 变更应有 overlay 或 controller 测试。
- 可见布局变化还需要 Windows 视觉/运行时检查；不能只凭测试声称 UI 无重叠。
