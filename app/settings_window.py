from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .models import Accent, AppSettings, DisplayMode, OverlayPosition, PronunciationContentMode, TtsProvider, VoxCpmDevice
from .version import APP_VERSION, formatted_changelog


_ENUM_LABELS = {
    DisplayMode.CARD: "卡片",
    DisplayMode.BARRAGE: "弹幕",
    OverlayPosition.NEAR_MOUSE: "鼠标附近",
    OverlayPosition.BOTTOM_RIGHT: "右下角",
    OverlayPosition.TOP_CENTER: "顶部居中",
    OverlayPosition.CENTER: "屏幕中央",
    OverlayPosition.RANDOM: "随机位置",
    Accent.UK: "英音",
    Accent.US: "美音",
    PronunciationContentMode.WORD: "只读单词",
    PronunciationContentMode.EXAMPLE: "只读例句",
    PronunciationContentMode.WORD_AND_EXAMPLE: "单词 + 例句",
    TtsProvider.SYSTEM_QT: "系统离线发音",
    TtsProvider.VOXCPM_LOCAL: "VoxCPM 本地服务",
    VoxCpmDevice.AUTO: "自动",
    VoxCpmDevice.CUDA: "CUDA",
    VoxCpmDevice.CPU: "CPU",
}


def _key_value(key: Any) -> int:
    value = getattr(key, "value", key)
    return int(value)


def _key_name(key: Any) -> str:
    key_value = _key_value(key)
    if ord("0") <= key_value <= ord("9"):
        return chr(key_value)
    if ord("A") <= key_value <= ord("Z"):
        return chr(key_value)

    f1 = _key_value(Qt.Key.Key_F1)
    f24 = _key_value(Qt.Key.Key_F24)
    if f1 <= key_value <= f24:
        return f"F{key_value - f1 + 1}"
    return ""


def _voxcpm_help_text() -> str:
    return """VoxCPM 参数操作文档

先按默认值使用。只有遇到首响慢、句中卡顿、短词漏读、显存不足或服务启动失败时，再一次只改一个参数并保存后重试。

基础流程
1. 发音引擎选择 VoxCPM 本地服务。
2. 优先点击“下载并导入运行时包”，运行时缺模型时再用“下载并导入模型包”。
3. 点击“检测服务”确认状态；需要立即使用时点击“启动服务”。
4. 修改目录、下载源或高级参数后，启动/检测/导入按钮会先应用当前窗口里的值。

常用服务参数
- 端点地址：桌面端访问本机 companion service 的 HTTP 地址。默认 http://127.0.0.1:8808。只支持本机地址。
- 请求超时：完整 WAV fallback 的网络等待上限。模型首次加载或完整生成较慢时可以调大。
- 安装目录：VoxCPM 运行时、service 脚本和日志目录。普通用户保持默认。
- 模型目录：VoxCPM2 模型文件目录。磁盘紧张时可以放到空间更大的盘。
- 使用时自动启动：只在选择 VoxCPM 本地服务并触发朗读时启动已导入的服务，不会自动下载模型。
- 语气提示词：传给 VoxCPM 的 voice prompt，例如 A calm English teacher voice.。过长或过复杂可能增加不稳定性。
- ModelScope 命名空间/仓库名/运行时包文件名/最低驱动版本：用于下载预构建运行时和模型包。除非你在切换资产，否则保持默认。

流式播放参数
- 流式预缓冲 voxcpm_stream_prebuffer_seconds：开播前先攒多少秒 PCM 音频。值越大，首响越慢但句中卡顿更少。默认 0.35；慢 GPU 可试 0.8 到 2.0。
- 预缓冲最大等待 voxcpm_stream_prebuffer_max_wait_seconds：墙钟等待上限。到点后只要已有有效 PCM 就先开播，避免为了攒满 2 秒音频而实际等 10 秒。慢 GPU 可试 1.5 到 3.0；如果仍卡顿，再增大流式预缓冲。
- 旧 service 如果没有 /synthesize_stream 并返回 404/405，会自动回退完整 WAV。此时预缓冲参数不会改善首响，需要重新导入新版运行时包。

VoxCPM 高级参数
- VOXCPM_DEVICE：auto 自动选择；cuda 强制用 NVIDIA GPU；cpu 强制 CPU。GPU 异常时可用 cpu 排查，但生成会明显变慢。
- VOXCPM_OPTIMIZE：启用模型优化。可能提升速度，也可能在某些环境加载失败；失败时服务会记录日志并用 optimize=false 重试。
- VOXCPM_CFG_VALUE：控制生成约束强度。默认 1.5。提高可能更贴合提示但更容易慢或不稳定；声音发飘或慢时先降到 1.2 到 1.5。
- inference_timesteps：推理步数。默认 10。步数越高通常越慢；5060 等较慢 GPU 可先试 6 到 8，质量不足再加回 10。
- retry_badcase：检测异常短音频并重试。短词漏读时保持开启；追求最快首响时可以关闭试验。
- retry_badcase_max_times：badcase 最大重试次数。默认 3。短词经常漏读可保持 3；想减少最坏等待可降到 1 或 2。
- retry_badcase_ratio_threshold：判断异常短音频的比例阈值。默认 4.0。阈值越敏感，越可能触发重试，也越可能增加等待。
- leading_silence_seconds：音频开头补静音。默认 0.12 秒。短词开头被吞时可略增到 0.15 到 0.25。
- trailing_silence_seconds：音频结尾补静音。默认 0.30 秒。尾音被截断时可略增到 0.35 到 0.50。

慢 GPU 调参顺序
1. 先看日志里的首字节耗时、达到预缓冲耗时、已缓冲音频秒数和生成倍率。
2. 如果生成倍率低于实时播放，先把 inference_timesteps 降到 6 到 8，再把 CFG value 降到 1.2 到 1.5。
3. 如果首响能接受但句中卡顿，把流式预缓冲提高到 0.8 到 2.0。
4. 如果开播前等待过久，把预缓冲最大等待设为 1.5 到 3.0，让已有 PCM 先开播。
5. 如果仍明显低于实时播放，改用完整 WAV fallback 或继续增大预缓冲。

建议
- 每次只改一个参数，保存后朗读同一个短词和同一句例句对比。
- 真实听感优先于数值。日志用于定位是首字节慢、预缓冲不足，还是生成速度低于实时。
- 参数改乱后，恢复默认值通常比继续叠加调整更可靠。"""


class HotkeyCaptureButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sequence = ""
        self._previous_sequence = ""
        self._capturing = False
        self.clicked.connect(self._start_capture)

    def sequence(self) -> str:
        return self._sequence

    def set_sequence(self, sequence: str) -> None:
        self._sequence = sequence.strip()
        self._previous_sequence = self._sequence
        self._capturing = False
        self.releaseKeyboard()
        self._refresh_text()

    def keyPressEvent(self, event: Any) -> None:
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        key_value = _key_value(key)
        if key_value == _key_value(Qt.Key.Key_Escape):
            self.set_sequence(self._previous_sequence)
            return
        if key_value in (
            _key_value(Qt.Key.Key_Backspace),
            _key_value(Qt.Key.Key_Delete),
        ):
            self.set_sequence("")
            return
        if key_value in (
            _key_value(Qt.Key.Key_Control),
            _key_value(Qt.Key.Key_Shift),
            _key_value(Qt.Key.Key_Alt),
            _key_value(Qt.Key.Key_Meta),
        ):
            return

        key_name = _key_name(key)
        if not key_name:
            self.setText("不支持这个键，请重试")
            return

        modifiers = event.modifiers()
        parts: list[str] = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Win")

        if not parts and not key_name.startswith("F"):
            self.setText("请按 Ctrl/Alt/Shift/Win + 键")
            return

        parts.append(key_name)
        self.set_sequence("+".join(parts))

    def focusOutEvent(self, event: Any) -> None:
        if self._capturing:
            self.set_sequence(self._previous_sequence)
        super().focusOutEvent(event)

    def _start_capture(self) -> None:
        self._previous_sequence = self._sequence
        self._capturing = True
        self.setText("请按快捷键...")
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.grabKeyboard()

    def _refresh_text(self) -> None:
        self.setText(self._sequence or "点击设置快捷键")


class SettingsDialog(QDialog):
    import_wordbook_requested = Signal()
    download_wordbook_requested = Signal()
    voxcpm_runtime_import_requested = Signal()
    voxcpm_runtime_download_requested = Signal()
    voxcpm_model_download_requested = Signal()
    voxcpm_model_import_requested = Signal()
    voxcpm_start_requested = Signal()
    voxcpm_stop_requested = Signal()
    voxcpm_health_check_requested = Signal()
    voxcpm_open_log_requested = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("oh my word 设置")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setModal(False)
        self.setMinimumSize(320, 280)

        self._tabs = QTabWidget(self)
        self._pronunciation_scroll = QScrollArea(self)
        self._display_mode = QComboBox(self)
        self._card_position = QComboBox(self)
        self._barrage_position = QComboBox(self)
        self._accent = QComboBox(self)
        self._pronunciation_content_mode = QComboBox(self)
        self._tts_provider = QComboBox(self)
        self._voxcpm_device = QComboBox(self)
        self._voxcpm_endpoint = QLineEdit(self)
        self._voxcpm_timeout = QSpinBox(self)
        self._voxcpm_stream_prebuffer = QDoubleSpinBox(self)
        self._voxcpm_stream_prebuffer_max_wait = QDoubleSpinBox(self)
        self._voxcpm_optimize = QCheckBox(self)
        self._voxcpm_cfg_value = QDoubleSpinBox(self)
        self._voxcpm_inference_timesteps = QSpinBox(self)
        self._voxcpm_retry_badcase = QCheckBox(self)
        self._voxcpm_retry_badcase_max_times = QSpinBox(self)
        self._voxcpm_retry_badcase_ratio_threshold = QDoubleSpinBox(self)
        self._voxcpm_leading_silence_seconds = QDoubleSpinBox(self)
        self._voxcpm_trailing_silence_seconds = QDoubleSpinBox(self)
        self._voxcpm_install_root = QLineEdit(self)
        self._voxcpm_model_cache_root = QLineEdit(self)
        self._voxcpm_use_model_mirror = QCheckBox(self)
        self._voxcpm_auto_start = QCheckBox(self)
        self._voxcpm_voice_prompt = QLineEdit(self)
        self._voxcpm_modelscope_namespace = QLineEdit(self)
        self._voxcpm_modelscope_repository = QLineEdit(self)
        self._voxcpm_modelscope_runtime_filename = QLineEdit(self)
        self._voxcpm_modelscope_min_driver_version = QLineEdit(self)
        self._voxcpm_install_status = QLabel("未检测", self)
        self._voxcpm_runtime_meta = QLabel("", self)
        self._voxcpm_service_status = QLabel("未检测", self)
        self._voxcpm_message = QLabel("", self)
        self._voxcpm_runtime_button = QPushButton("导入 VoxCPM 运行时包", self)
        self._voxcpm_runtime_download_button = QPushButton("下载并导入运行时包", self)
        self._voxcpm_model_download_button = QPushButton("下载并导入模型包", self)
        self._voxcpm_model_button = QPushButton("导入模型包", self)
        self._voxcpm_start_button = QPushButton("启动服务", self)
        self._voxcpm_stop_button = QPushButton("停止服务", self)
        self._voxcpm_check_button = QPushButton("检测服务", self)
        self._voxcpm_open_log_button = QPushButton("打开日志", self)
        self._voxcpm_install_browse_button = QPushButton("选择", self)
        self._voxcpm_model_browse_button = QPushButton("选择", self)
        self._voxcpm_advanced_group = QGroupBox("VoxCPM 高级参数", self)
        self._voxcpm_advanced_content = QWidget(self._voxcpm_advanced_group)
        self._enabled = QCheckBox(self)
        self._mute = QCheckBox(self)
        self._auto_pronounce_on_popup = QCheckBox(self)
        self._min_delay = QSpinBox(self)
        self._max_delay = QSpinBox(self)
        self._activity_threshold = QSpinBox(self)
        self._activity_weight = QSpinBox(self)
        self._popup_duration = QSpinBox(self)
        self._snooze_minutes = QSpinBox(self)
        self._auto_pronounce_delay = QDoubleSpinBox(self)
        self._pronounce_hotkey = HotkeyCaptureButton(self)
        self._toggle_detail_hotkey = HotkeyCaptureButton(self)
        self._trigger_now_hotkey = HotkeyCaptureButton(self)
        self._mark_mastered_hotkey = HotkeyCaptureButton(self)
        self._known_hotkey = HotkeyCaptureButton(self)
        self._unknown_hotkey = HotkeyCaptureButton(self)
        self._dismiss_hotkey = HotkeyCaptureButton(self)
        self._import_wordbook_button = QPushButton("导入词库...", self)
        self._download_wordbook_button = QPushButton("下载推荐考研词库", self)
        self._voxcpm_help_view = QPlainTextEdit(self)
        self._version_label = QLabel(f"当前版本：v{APP_VERSION}", self)
        self._changelog_view = QPlainTextEdit(self)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )

        self._build_ui()
        self.set_settings(settings)

        save_button = self._buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText("保存")
        if cancel_button is not None:
            cancel_button.setText("取消")

        self._enabled.toggled.connect(lambda _: self._refresh_toggle_labels())
        self._mute.toggled.connect(lambda _: self._refresh_toggle_labels())
        self._auto_pronounce_on_popup.toggled.connect(lambda _: self._refresh_toggle_labels())
        self._voxcpm_use_model_mirror.toggled.connect(lambda _: self._refresh_toggle_labels())
        self._voxcpm_auto_start.toggled.connect(lambda _: self._refresh_toggle_labels())
        self._voxcpm_optimize.toggled.connect(lambda _: self._refresh_toggle_labels())
        self._voxcpm_retry_badcase.toggled.connect(lambda _: self._refresh_toggle_labels())
        self._voxcpm_advanced_group.toggled.connect(self._voxcpm_advanced_content.setVisible)
        self._import_wordbook_button.clicked.connect(self.import_wordbook_requested.emit)
        self._download_wordbook_button.clicked.connect(self.download_wordbook_requested.emit)
        self._voxcpm_runtime_button.clicked.connect(self.voxcpm_runtime_import_requested.emit)
        self._voxcpm_runtime_download_button.clicked.connect(self.voxcpm_runtime_download_requested.emit)
        self._voxcpm_model_download_button.clicked.connect(self.voxcpm_model_download_requested.emit)
        self._voxcpm_model_button.clicked.connect(self.voxcpm_model_import_requested.emit)
        self._voxcpm_start_button.clicked.connect(self.voxcpm_start_requested.emit)
        self._voxcpm_stop_button.clicked.connect(self.voxcpm_stop_requested.emit)
        self._voxcpm_check_button.clicked.connect(self.voxcpm_health_check_requested.emit)
        self._voxcpm_open_log_button.clicked.connect(self.voxcpm_open_log_requested.emit)
        self._voxcpm_install_browse_button.clicked.connect(
            lambda: self._browse_directory(self._voxcpm_install_root, "选择 VoxCPM 安装目录")
        )
        self._voxcpm_model_browse_button.clicked.connect(
            lambda: self._browse_directory(self._voxcpm_model_cache_root, "选择 VoxCPM 模型目录")
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

    def set_settings(self, settings: AppSettings) -> None:
        self._enabled.setChecked(settings.enabled)
        self._mute.setChecked(settings.mute_pronunciation)
        self._set_enum_value(self._display_mode, settings.display_mode)
        self._set_enum_value(self._card_position, settings.card_position)
        self._set_enum_value(self._barrage_position, settings.barrage_position)
        self._set_enum_value(self._accent, settings.accent)
        self._set_enum_value(self._pronunciation_content_mode, settings.pronunciation_content_mode)
        self._set_enum_value(self._tts_provider, settings.tts_provider)
        self._set_enum_value(self._voxcpm_device, settings.voxcpm_device)
        self._voxcpm_endpoint.setText(settings.voxcpm_endpoint)
        self._voxcpm_timeout.setValue(settings.voxcpm_timeout_seconds)
        self._voxcpm_stream_prebuffer.setValue(settings.voxcpm_stream_prebuffer_seconds)
        self._voxcpm_stream_prebuffer_max_wait.setValue(settings.voxcpm_stream_prebuffer_max_wait_seconds)
        self._voxcpm_optimize.setChecked(settings.voxcpm_optimize)
        self._voxcpm_cfg_value.setValue(settings.voxcpm_cfg_value)
        self._voxcpm_inference_timesteps.setValue(settings.voxcpm_inference_timesteps)
        self._voxcpm_retry_badcase.setChecked(settings.voxcpm_retry_badcase)
        self._voxcpm_retry_badcase_max_times.setValue(settings.voxcpm_retry_badcase_max_times)
        self._voxcpm_retry_badcase_ratio_threshold.setValue(settings.voxcpm_retry_badcase_ratio_threshold)
        self._voxcpm_leading_silence_seconds.setValue(settings.voxcpm_leading_silence_seconds)
        self._voxcpm_trailing_silence_seconds.setValue(settings.voxcpm_trailing_silence_seconds)
        self._voxcpm_install_root.setText(settings.voxcpm_install_root)
        self._voxcpm_model_cache_root.setText(settings.voxcpm_model_cache_root)
        self._voxcpm_use_model_mirror.setChecked(settings.voxcpm_use_model_mirror)
        self._voxcpm_auto_start.setChecked(settings.voxcpm_auto_start)
        self._voxcpm_voice_prompt.setText(settings.voxcpm_voice_prompt)
        self._voxcpm_modelscope_namespace.setText(settings.voxcpm_modelscope_namespace)
        self._voxcpm_modelscope_repository.setText(settings.voxcpm_modelscope_repository)
        self._voxcpm_modelscope_runtime_filename.setText(settings.voxcpm_modelscope_runtime_filename)
        self._voxcpm_modelscope_min_driver_version.setText(settings.voxcpm_modelscope_min_driver_version)
        self._min_delay.setValue(settings.min_delay_minutes)
        self._max_delay.setValue(settings.max_delay_minutes)
        self._activity_threshold.setValue(settings.activity_threshold_per_minute)
        self._activity_weight.setValue(settings.activity_slowdown_weight)
        self._popup_duration.setValue(settings.popup_duration_seconds)
        self._snooze_minutes.setValue(settings.snooze_minutes)
        self._auto_pronounce_on_popup.setChecked(settings.auto_pronounce_on_popup)
        self._auto_pronounce_delay.setValue(settings.auto_pronounce_delay_seconds)
        self._pronounce_hotkey.set_sequence(settings.pronounce_hotkey)
        self._toggle_detail_hotkey.set_sequence(settings.toggle_detail_hotkey)
        self._trigger_now_hotkey.set_sequence(settings.trigger_now_hotkey)
        self._mark_mastered_hotkey.set_sequence(settings.mark_mastered_hotkey)
        self._known_hotkey.set_sequence(settings.known_hotkey)
        self._unknown_hotkey.set_sequence(settings.unknown_hotkey)
        self._dismiss_hotkey.set_sequence(settings.dismiss_hotkey)
        self._refresh_toggle_labels()

    def get_settings(self) -> AppSettings:
        return AppSettings(
            enabled=self._enabled.isChecked(),
            display_mode=self._current_enum_value(self._display_mode, DisplayMode, AppSettings().display_mode),
            card_position=self._current_enum_value(self._card_position, OverlayPosition, AppSettings().card_position),
            barrage_position=self._current_enum_value(
                self._barrage_position,
                OverlayPosition,
                AppSettings().barrage_position,
            ),
            min_delay_minutes=self._min_delay.value(),
            max_delay_minutes=self._max_delay.value(),
            activity_threshold_per_minute=self._activity_threshold.value(),
            activity_slowdown_weight=self._activity_weight.value(),
            popup_duration_seconds=self._popup_duration.value(),
            snooze_minutes=self._snooze_minutes.value(),
            auto_pronounce_on_popup=self._auto_pronounce_on_popup.isChecked(),
            auto_pronounce_delay_seconds=self._auto_pronounce_delay.value(),
            mute_pronunciation=self._mute.isChecked(),
            pronunciation_content_mode=self._current_enum_value(
                self._pronunciation_content_mode,
                PronunciationContentMode,
                AppSettings().pronunciation_content_mode,
            ),
            accent=self._current_enum_value(self._accent, Accent, AppSettings().accent),
            tts_provider=self._current_enum_value(self._tts_provider, TtsProvider, AppSettings().tts_provider),
            voxcpm_device=self._current_enum_value(self._voxcpm_device, VoxCpmDevice, AppSettings().voxcpm_device),
            voxcpm_endpoint=self._voxcpm_endpoint.text().strip() or AppSettings().voxcpm_endpoint,
            voxcpm_timeout_seconds=self._voxcpm_timeout.value(),
            voxcpm_stream_prebuffer_seconds=self._voxcpm_stream_prebuffer.value(),
            voxcpm_stream_prebuffer_max_wait_seconds=self._voxcpm_stream_prebuffer_max_wait.value(),
            voxcpm_optimize=self._voxcpm_optimize.isChecked(),
            voxcpm_cfg_value=self._voxcpm_cfg_value.value(),
            voxcpm_inference_timesteps=self._voxcpm_inference_timesteps.value(),
            voxcpm_retry_badcase=self._voxcpm_retry_badcase.isChecked(),
            voxcpm_retry_badcase_max_times=self._voxcpm_retry_badcase_max_times.value(),
            voxcpm_retry_badcase_ratio_threshold=self._voxcpm_retry_badcase_ratio_threshold.value(),
            voxcpm_leading_silence_seconds=self._voxcpm_leading_silence_seconds.value(),
            voxcpm_trailing_silence_seconds=self._voxcpm_trailing_silence_seconds.value(),
            voxcpm_install_root=self._voxcpm_install_root.text().strip() or AppSettings().voxcpm_install_root,
            voxcpm_model_cache_root=self._voxcpm_model_cache_root.text().strip()
            or AppSettings().voxcpm_model_cache_root,
            voxcpm_use_model_mirror=self._voxcpm_use_model_mirror.isChecked(),
            voxcpm_auto_start=self._voxcpm_auto_start.isChecked(),
            voxcpm_voice_prompt=self._voxcpm_voice_prompt.text().strip(),
            voxcpm_modelscope_namespace=self._voxcpm_modelscope_namespace.text().strip()
            or AppSettings().voxcpm_modelscope_namespace,
            voxcpm_modelscope_repository=self._voxcpm_modelscope_repository.text().strip()
            or AppSettings().voxcpm_modelscope_repository,
            voxcpm_modelscope_runtime_filename=self._voxcpm_modelscope_runtime_filename.text().strip()
            or AppSettings().voxcpm_modelscope_runtime_filename,
            voxcpm_modelscope_min_driver_version=self._voxcpm_modelscope_min_driver_version.text().strip()
            or AppSettings().voxcpm_modelscope_min_driver_version,
            pronounce_hotkey=self._pronounce_hotkey.sequence() or AppSettings().pronounce_hotkey,
            toggle_detail_hotkey=self._toggle_detail_hotkey.sequence() or AppSettings().toggle_detail_hotkey,
            trigger_now_hotkey=self._trigger_now_hotkey.sequence() or AppSettings().trigger_now_hotkey,
            mark_mastered_hotkey=self._mark_mastered_hotkey.sequence() or AppSettings().mark_mastered_hotkey,
            known_hotkey=self._known_hotkey.sequence() or AppSettings().known_hotkey,
            unknown_hotkey=self._unknown_hotkey.sequence() or AppSettings().unknown_hotkey,
            dismiss_hotkey=self._dismiss_hotkey.sequence() or AppSettings().dismiss_hotkey,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        hint = QLabel(
            "保存后立即生效。快捷键建议使用 Ctrl+Alt+数字，也支持 Shift、字母和 F1-F24；"
            "如果被其他软件占用，托盘会提示。",
            self,
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        for member in DisplayMode:
            self._display_mode.addItem(_ENUM_LABELS.get(member, member.value), member)
        for member in OverlayPosition:
            self._card_position.addItem(_ENUM_LABELS.get(member, member.value), member)
            self._barrage_position.addItem(_ENUM_LABELS.get(member, member.value), member)
        for member in Accent:
            self._accent.addItem(_ENUM_LABELS.get(member, member.value), member)
        for member in PronunciationContentMode:
            self._pronunciation_content_mode.addItem(_ENUM_LABELS.get(member, member.value), member)
        for member in TtsProvider:
            self._tts_provider.addItem(_ENUM_LABELS.get(member, member.value), member)
        for member in VoxCpmDevice:
            self._voxcpm_device.addItem(_ENUM_LABELS.get(member, member.value), member)

        for spin in (self._min_delay, self._max_delay):
            spin.setRange(1, 240)
            spin.setSuffix(" 分钟")

        self._activity_threshold.setRange(1, 600)
        self._activity_threshold.setSuffix(" 次/分钟")

        self._activity_weight.setRange(0, 300)
        self._activity_weight.setSuffix(" %")

        self._popup_duration.setRange(1, 600)
        self._popup_duration.setSuffix(" 秒")

        self._snooze_minutes.setRange(1, 240)
        self._snooze_minutes.setSuffix(" 分钟")
        self._auto_pronounce_delay.setRange(0.0, 10.0)
        self._auto_pronounce_delay.setDecimals(2)
        self._auto_pronounce_delay.setSingleStep(0.05)
        self._auto_pronounce_delay.setSuffix(" 秒")

        self._voxcpm_endpoint.setPlaceholderText(AppSettings().voxcpm_endpoint)
        self._voxcpm_voice_prompt.setPlaceholderText("A calm English teacher voice, clear pronunciation.")
        self._voxcpm_timeout.setRange(1, 120)
        self._voxcpm_timeout.setSuffix(" 秒")
        self._voxcpm_stream_prebuffer.setRange(0.0, 2.0)
        self._voxcpm_stream_prebuffer.setDecimals(2)
        self._voxcpm_stream_prebuffer.setSingleStep(0.05)
        self._voxcpm_stream_prebuffer.setSuffix(" 秒")
        self._voxcpm_stream_prebuffer.setToolTip(
            "按音频时长预缓冲；慢 GPU 可适当增大，但会增加首响等待。"
        )
        self._voxcpm_stream_prebuffer_max_wait.setRange(0.1, 30.0)
        self._voxcpm_stream_prebuffer_max_wait.setDecimals(2)
        self._voxcpm_stream_prebuffer_max_wait.setSingleStep(0.1)
        self._voxcpm_stream_prebuffer_max_wait.setSuffix(" 秒")
        self._voxcpm_stream_prebuffer_max_wait.setToolTip(
            "达到该墙钟上限后，只要已有有效 PCM 就先开播，避免慢 GPU 长时间等满目标预缓冲。"
        )
        self._voxcpm_cfg_value.setRange(0.1, 10.0)
        self._voxcpm_cfg_value.setDecimals(2)
        self._voxcpm_cfg_value.setSingleStep(0.1)
        self._voxcpm_inference_timesteps.setRange(1, 100)
        self._voxcpm_retry_badcase_max_times.setRange(0, 10)
        self._voxcpm_retry_badcase_ratio_threshold.setRange(0.1, 20.0)
        self._voxcpm_retry_badcase_ratio_threshold.setDecimals(2)
        self._voxcpm_retry_badcase_ratio_threshold.setSingleStep(0.1)
        for silence_spin in (self._voxcpm_leading_silence_seconds, self._voxcpm_trailing_silence_seconds):
            silence_spin.setRange(0.0, 2.0)
            silence_spin.setDecimals(2)
            silence_spin.setSingleStep(0.05)
            silence_spin.setSuffix(" 秒")
        for line_edit in (
            self._voxcpm_endpoint,
            self._voxcpm_install_root,
            self._voxcpm_model_cache_root,
            self._voxcpm_voice_prompt,
            self._voxcpm_modelscope_namespace,
            self._voxcpm_modelscope_repository,
            self._voxcpm_modelscope_runtime_filename,
            self._voxcpm_modelscope_min_driver_version,
        ):
            line_edit.setMinimumWidth(80)
            line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            line_edit.setClearButtonEnabled(True)

        self._voxcpm_message.setWordWrap(True)
        self._voxcpm_runtime_meta.setWordWrap(True)
        self._tabs.addTab(self._scrollable_tab(self._build_learning_tab()), "学习")
        self._tabs.addTab(self._scrollable_tab(self._build_display_tab()), "显示")
        self._pronunciation_scroll = self._scrollable_tab(self._build_pronunciation_tab())
        self._tabs.addTab(self._pronunciation_scroll, "发音")
        self._tabs.addTab(self._scrollable_tab(self._build_hotkeys_tab()), "快捷键")
        self._tabs.addTab(self._scrollable_tab(self._build_wordbooks_tab()), "词库")
        self._tabs.addTab(self._build_help_tab(), "帮助")
        self._tabs.addTab(self._build_about_tab(), "关于")
        root.addWidget(self._tabs, 1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        buttons_row.addWidget(self._buttons)
        root.addLayout(buttons_row)
        self._resize_to_available_screen()

    def _build_learning_tab(self) -> QWidget:
        widget = QWidget(self)
        form = self._new_form(widget)
        form.addRow(self._enabled)
        form.addRow("最短间隔", self._min_delay)
        form.addRow("最长间隔", self._max_delay)
        form.addRow("高频操作阈值", self._activity_threshold)
        form.addRow("频率影响权重", self._activity_weight)
        form.addRow("稍后时长", self._snooze_minutes)
        return widget

    def _build_display_tab(self) -> QWidget:
        widget = QWidget(self)
        form = self._new_form(widget)
        form.addRow("显示方式", self._display_mode)
        form.addRow("卡片位置", self._card_position)
        form.addRow("弹幕位置", self._barrage_position)
        form.addRow("卡片停留时长", self._popup_duration)
        return widget

    def _build_pronunciation_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        engine_group = QGroupBox("发音引擎", widget)
        engine_form = self._new_form(engine_group)
        engine_form.addRow(self._mute)
        engine_form.addRow(self._auto_pronounce_on_popup)
        engine_form.addRow("自动朗读延迟", self._auto_pronounce_delay)
        engine_form.addRow("朗读内容", self._pronunciation_content_mode)
        engine_form.addRow("发音口音", self._accent)
        engine_form.addRow("发音引擎", self._tts_provider)
        layout.addWidget(engine_group)

        service_group = QGroupBox("VoxCPM 本地服务", widget)
        service_layout = QVBoxLayout(service_group)
        service_layout.setSpacing(10)

        status_form = QFormLayout()
        status_form.addRow("安装状态", self._voxcpm_install_status)
        status_form.addRow("运行时信息", self._voxcpm_runtime_meta)
        status_form.addRow("服务状态", self._voxcpm_service_status)
        status_form.addRow("状态信息", self._voxcpm_message)
        service_layout.addLayout(status_form)

        settings_form = QFormLayout()
        settings_form.setSpacing(10)
        settings_form.addRow("端点地址", self._voxcpm_endpoint)
        settings_form.addRow("请求超时", self._voxcpm_timeout)
        settings_form.addRow("流式预缓冲", self._voxcpm_stream_prebuffer)
        settings_form.addRow("预缓冲最大等待", self._voxcpm_stream_prebuffer_max_wait)
        settings_form.addRow("安装目录", self._path_row(self._voxcpm_install_root, self._voxcpm_install_browse_button))
        settings_form.addRow(
            "模型目录",
            self._path_row(self._voxcpm_model_cache_root, self._voxcpm_model_browse_button),
        )
        settings_form.addRow(self._voxcpm_use_model_mirror)
        settings_form.addRow(self._voxcpm_auto_start)
        settings_form.addRow("语气提示词", self._voxcpm_voice_prompt)
        settings_form.addRow("ModelScope 命名空间", self._voxcpm_modelscope_namespace)
        settings_form.addRow("ModelScope 仓库名", self._voxcpm_modelscope_repository)
        settings_form.addRow("运行时包文件名", self._voxcpm_modelscope_runtime_filename)
        settings_form.addRow("最低驱动版本", self._voxcpm_modelscope_min_driver_version)
        service_layout.addLayout(settings_form)

        service_layout.addLayout(
            self._button_grid(
                [
                    self._voxcpm_runtime_download_button,
                    self._voxcpm_model_download_button,
                    self._voxcpm_runtime_button,
                    self._voxcpm_model_button,
                    self._voxcpm_start_button,
                    self._voxcpm_stop_button,
                    self._voxcpm_check_button,
                    self._voxcpm_open_log_button,
                ]
            )
        )
        layout.addWidget(service_group)

        self._voxcpm_advanced_group.setCheckable(True)
        self._voxcpm_advanced_group.setChecked(False)
        advanced_layout = QVBoxLayout(self._voxcpm_advanced_group)
        advanced_layout.setContentsMargins(12, 12, 12, 12)
        advanced_form = self._new_form(self._voxcpm_advanced_content)
        advanced_form.addRow("计算设备", self._voxcpm_device)
        advanced_form.addRow(self._voxcpm_optimize)
        advanced_form.addRow("CFG value", self._voxcpm_cfg_value)
        advanced_form.addRow("inference_timesteps", self._voxcpm_inference_timesteps)
        advanced_form.addRow(self._voxcpm_retry_badcase)
        advanced_form.addRow("retry_badcase_max_times", self._voxcpm_retry_badcase_max_times)
        advanced_form.addRow("retry_badcase_ratio_threshold", self._voxcpm_retry_badcase_ratio_threshold)
        advanced_form.addRow("leading_silence_seconds", self._voxcpm_leading_silence_seconds)
        advanced_form.addRow("trailing_silence_seconds", self._voxcpm_trailing_silence_seconds)
        advanced_layout.addWidget(self._voxcpm_advanced_content)
        self._voxcpm_advanced_content.setVisible(False)
        layout.addWidget(self._voxcpm_advanced_group)
        layout.addStretch(1)
        return widget

    def _build_hotkeys_tab(self) -> QWidget:
        widget = QWidget(self)
        form = self._new_form(widget)
        form.addRow("朗读快捷键", self._pronounce_hotkey)
        form.addRow("展开详情快捷键", self._toggle_detail_hotkey)
        form.addRow("立刻弹出快捷键", self._trigger_now_hotkey)
        form.addRow("标记掌握快捷键", self._mark_mastered_hotkey)
        form.addRow("认识快捷键", self._known_hotkey)
        form.addRow("不认识快捷键", self._unknown_hotkey)
        form.addRow("关闭快捷键", self._dismiss_hotkey)
        return widget

    def _build_wordbooks_tab(self) -> QWidget:
        widget = QWidget(self)
        form = self._new_form(widget)
        form.addRow("导入本地词库", self._import_wordbook_button)
        form.addRow("推荐词库", self._download_wordbook_button)
        return widget

    def _build_help_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        self._voxcpm_help_view.setReadOnly(True)
        self._voxcpm_help_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._voxcpm_help_view.setPlainText(_voxcpm_help_text())

        layout.addWidget(self._voxcpm_help_view, 1)
        return widget

    def _build_about_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        self._version_label.setText(f"当前版本：v{APP_VERSION}")
        self._changelog_view.setReadOnly(True)
        self._changelog_view.setPlainText(formatted_changelog())

        layout.addWidget(self._version_label)
        layout.addWidget(self._changelog_view, 1)
        return widget

    @staticmethod
    def _new_form(parent: QWidget) -> QFormLayout:
        form = QFormLayout(parent)
        form.setContentsMargins(0, 12, 0, 0)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        return form

    @staticmethod
    def _path_row(line_edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return widget

    @staticmethod
    def _button_grid(buttons: list[QPushButton]) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for index, button in enumerate(buttons):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(button, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return grid

    @staticmethod
    def _scrollable_tab(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    def _resize_to_available_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(680, 620)
            return
        available = screen.availableGeometry()
        width = min(680, max(320, available.width() - 80))
        height = min(620, max(280, available.height() - 80))
        self.resize(width, height)

    def set_voxcpm_download_progress(self, stage: str) -> None:
        self._voxcpm_message.setText(stage)

    def set_voxcpm_status(self, status: object) -> None:
        installed = bool(getattr(status, "installed", False))
        running = bool(getattr(status, "running", False))
        installing = bool(getattr(status, "installing", False))
        busy = bool(getattr(status, "busy", False))
        message = str(getattr(status, "message", "") or "")
        log_path = getattr(status, "log_path", None)
        runtime_state = str(getattr(status, "runtime_state", "") or "")
        runtime_id = str(getattr(status, "runtime_id", "") or "")
        cuda_tag = str(getattr(status, "cuda_tag", "") or "")
        min_driver_version = str(getattr(status, "min_driver_version", "") or "")
        model_version = str(getattr(status, "model_version", "") or "")

        if installing:
            install_status = "安装中"
        elif busy:
            install_status = "处理中"
        elif runtime_state == "imported":
            install_status = "已导入"
        elif runtime_state == "legacy":
            install_status = "已安装（旧版）"
        elif runtime_state == "broken":
            install_status = "损坏"
        else:
            install_status = "未导入" if not installed else "已安装"

        runtime_meta_parts = []
        if runtime_id:
            runtime_meta_parts.append(f"ID: {runtime_id}")
        if cuda_tag:
            runtime_meta_parts.append(f"CUDA: {cuda_tag}")
        if min_driver_version:
            runtime_meta_parts.append(f"最低驱动: {min_driver_version}")
        if model_version:
            runtime_meta_parts.append(f"模型: {model_version}")

        self._voxcpm_install_status.setText(install_status)
        self._voxcpm_runtime_meta.setText(" | ".join(runtime_meta_parts))
        self._voxcpm_service_status.setText("运行中" if running else "未运行")
        self._voxcpm_message.setText(message or (f"日志：{log_path}" if log_path else ""))
        self._voxcpm_runtime_button.setEnabled(not busy)
        self._voxcpm_runtime_download_button.setEnabled(not busy)
        self._voxcpm_model_download_button.setEnabled(not busy)
        self._voxcpm_model_button.setEnabled(not busy)
        self._voxcpm_start_button.setEnabled(installed and not running and not busy)
        self._voxcpm_stop_button.setEnabled(running)
        self._voxcpm_open_log_button.setEnabled(log_path is not None)

    def _browse_directory(self, target: QLineEdit, title: str) -> None:
        selected = QFileDialog.getExistingDirectory(self, title, target.text().strip())
        if selected:
            target.setText(selected)

    @staticmethod
    def _set_enum_value(combo: QComboBox, value: object) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    @staticmethod
    def _current_enum_value(combo: QComboBox, enum_type: Any, default: object) -> object:
        data = combo.currentData()
        if isinstance(data, enum_type):
            return data
        try:
            return enum_type(data)
        except (TypeError, ValueError):
            return default

    def _refresh_toggle_labels(self) -> None:
        self._enabled.setText(
            "自动学习：已开启（取消勾选会暂停）"
            if self._enabled.isChecked()
            else "自动学习：已暂停（勾选会继续）"
        )
        self._mute.setText(
            "发音：已静音（取消勾选恢复）"
            if self._mute.isChecked()
            else "发音：正常播放（勾选后静音）"
        )
        self._auto_pronounce_on_popup.setText(
            "弹窗：自动朗读当前单词"
            if self._auto_pronounce_on_popup.isChecked()
            else "弹窗：不自动朗读"
        )
        self._voxcpm_use_model_mirror.setText(
            "下载：优先使用国内镜像 / ModelScope"
            if self._voxcpm_use_model_mirror.isChecked()
            else "下载：使用默认源"
        )
        self._voxcpm_auto_start.setText(
            "VoxCPM：使用时自动启动本地服务"
            if self._voxcpm_auto_start.isChecked()
            else "VoxCPM：不自动启动服务"
        )
        self._voxcpm_optimize.setText(
            "VOXCPM_OPTIMIZE：启用（失败时服务端回退）"
            if self._voxcpm_optimize.isChecked()
            else "VOXCPM_OPTIMIZE：关闭（兼容优先）"
        )
        self._voxcpm_retry_badcase.setText(
            "retry_badcase：启用异常短音频重试"
            if self._voxcpm_retry_badcase.isChecked()
            else "retry_badcase：关闭异常短音频重试"
        )
