# 弹窗控制实现计划

> **给 agent worker 的要求：** 必须使用子技能 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐步执行本计划。步骤使用 checkbox（`- [ ]`）语法，便于跟踪。

**目标：** 增加卡片随机位置、修正弹幕退出行为、支持仅在弹窗可见时生效的操作快捷键、保持 IPA 可见，并产出新的 Windows 包。

**架构：** 保持 `AppController` 作为协调层，扩展 `AppSettings` 和 `GlobalHotkeyService` 以支持新动作，并在现有 overlay 模块内部做局部几何/布局修复。尽量复用现有弹窗行为，只有在重复变得明显时才抽取小 helper。

**技术栈：** Python 3.11、PySide6、pytest、PyInstaller

---

### 任务 1：用失败测试锁定行为

**文件：**
- 新建：`tests/test_overlays.py`
- 修改：`tests/test_settings.py`
- 修改：`tests/test_controller.py`

- [ ] **步骤 1：编写失败测试**

添加测试覆盖：
- 卡片随机位置保持在屏幕边界内
- 弹幕漂移到完全离屏后才结束
- 设置能够加载/保存新的 `known`、`unknown` 和 `dismiss` 快捷键
- controller 中仅弹窗可见时生效的动作：无可见弹窗时不做事，可见时正确分发

- [ ] **步骤 2：运行目标测试并确认失败**

运行：`python -m pytest tests/test_settings.py tests/test_controller.py tests/test_overlays.py -q`

预期：由于缺少设置字段、缺少弹窗动作 handler、几何行为不正确而失败。

### 任务 2：实现设置和热键模型变更

**文件：**
- 修改：`app/models.py`
- 修改：`app/settings.py`
- 修改：`app/settings_window.py`
- 修改：`app/hotkeys.py`

- [ ] **步骤 1：添加新的设置字段和默认值**

向 `AppSettings` 增加 `known_hotkey`、`unknown_hotkey` 和 `dismiss_hotkey`，并设置稳定默认值。

- [ ] **步骤 2：持久化并规范化新字段**

扩展 `SettingsStore` 的 load/save 规范化和序列化，让新快捷键字段按现有设置行为往返保存。

- [ ] **步骤 3：在设置 UI 中暴露新的快捷键编辑器**

在设置对话框中增加三个快捷键捕获控件，标签分别为 `认识`、`不认识` 和 `关闭`。

- [ ] **步骤 4：扩展全局热键注册**

从 `GlobalHotkeyService` 注册和分发三个新动作，同时不改变现有快捷键行为。

- [ ] **步骤 5：重新运行目标测试**

运行：`python -m pytest tests/test_settings.py tests/test_controller.py tests/test_overlays.py -q`

预期：设置相关失败已解决；弹窗行为测试可能仍失败。

### 任务 3：实现可见弹窗动作和几何修复

**文件：**
- 修改：`app/controller.py`
- 修改：`app/overlays/card_popup.py`
- 修改：`app/overlays/barrage_popup.py`

- [ ] **步骤 1：为仅可见弹窗动作接入 controller handler**

新增 controller 方法：只有当前存在可见弹窗并且有 active word 时，才应用 `known`、`unknown` 和 `dismiss`。

- [ ] **步骤 2：启用真正随机的卡片位置**

允许卡片设置使用 `OverlayPosition.RANDOM`，并在每次 `show_popup()` 时生成一个新的、边界内的随机坐标。

- [ ] **步骤 3：修正弹幕退出几何**

修正弹幕动画结束坐标，让弹窗完整离开屏幕后才关闭。

- [ ] **步骤 4：修复弹幕头部布局**

重新平衡弹幕文本区和动作区布局，让 IPA 文本在正常内容压力下仍保持可见。

- [ ] **步骤 5：重新运行目标测试**

运行：`python -m pytest tests/test_settings.py tests/test_controller.py tests/test_overlays.py -q`

预期：所有目标测试通过。

### 任务 4：验证、重启并打包

**文件：**
- 只修改 `build/` 输出

- [ ] **步骤 1：运行完整测试套件**

运行：`python -m pytest tests -q`

预期：全部通过。

- [ ] **步骤 2：用新代码重启本地应用**

重启正在运行的 Python 进程，确保当前线程使用新的弹窗行为。

- [ ] **步骤 3：构建 Windows 包**

运行：`.\build\build_exe.ps1`

预期：PyInstaller 完成，并在 `dist/` 下写入新输出。

- [ ] **步骤 4：汇报包路径和验证证据**

返回准确构建输出路径，以及测试和构建成功结果。
