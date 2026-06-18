from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .models import Accent, AppSettings, DisplayMode, OverlayPosition, PronunciationContentMode, TtsProvider
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
    voxcpm_model_import_requested = Signal()
    voxcpm_install_requested = Signal()
    voxcpm_start_requested = Signal()
    voxcpm_stop_requested = Signal()
    voxcpm_health_check_requested = Signal()
    voxcpm_open_log_requested = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("oh my word 设置")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setModal(False)
        self.resize(680, 620)

        self._tabs = QTabWidget(self)
        self._display_mode = QComboBox(self)
        self._card_position = QComboBox(self)
        self._barrage_position = QComboBox(self)
        self._accent = QComboBox(self)
        self._pronunciation_content_mode = QComboBox(self)
        self._tts_provider = QComboBox(self)
        self._voxcpm_endpoint = QLineEdit(self)
        self._voxcpm_timeout = QSpinBox(self)
        self._voxcpm_stream_prebuffer = QDoubleSpinBox(self)
        self._voxcpm_install_root = QLineEdit(self)
        self._voxcpm_model_cache_root = QLineEdit(self)
        self._voxcpm_use_model_mirror = QCheckBox(self)
        self._voxcpm_auto_start = QCheckBox(self)
        self._voxcpm_voice_prompt = QLineEdit(self)
        self._voxcpm_install_status = QLabel("未检测", self)
        self._voxcpm_runtime_meta = QLabel("", self)
        self._voxcpm_service_status = QLabel("未检测", self)
        self._voxcpm_message = QLabel("", self)
        self._voxcpm_runtime_button = QPushButton("导入 VoxCPM 运行时包", self)
        self._voxcpm_runtime_download_button = QPushButton("下载并导入运行时包", self)
        self._voxcpm_model_button = QPushButton("导入模型包", self)
        self._voxcpm_install_button = QPushButton("后台安装 / 更新", self)
        self._voxcpm_start_button = QPushButton("启动服务", self)
        self._voxcpm_stop_button = QPushButton("停止服务", self)
        self._voxcpm_check_button = QPushButton("检测服务", self)
        self._voxcpm_open_log_button = QPushButton("打开日志", self)
        self._voxcpm_install_browse_button = QPushButton("选择", self)
        self._voxcpm_model_browse_button = QPushButton("选择", self)
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
        self._import_wordbook_button.clicked.connect(self.import_wordbook_requested.emit)
        self._download_wordbook_button.clicked.connect(self.download_wordbook_requested.emit)
        self._voxcpm_runtime_button.clicked.connect(self.voxcpm_runtime_import_requested.emit)
        self._voxcpm_runtime_download_button.clicked.connect(self.voxcpm_runtime_download_requested.emit)
        self._voxcpm_model_button.clicked.connect(self.voxcpm_model_import_requested.emit)
        self._voxcpm_install_button.clicked.connect(self.voxcpm_install_requested.emit)
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
        self._voxcpm_endpoint.setText(settings.voxcpm_endpoint)
        self._voxcpm_timeout.setValue(settings.voxcpm_timeout_seconds)
        self._voxcpm_stream_prebuffer.setValue(settings.voxcpm_stream_prebuffer_seconds)
        self._voxcpm_install_root.setText(settings.voxcpm_install_root)
        self._voxcpm_model_cache_root.setText(settings.voxcpm_model_cache_root)
        self._voxcpm_use_model_mirror.setChecked(settings.voxcpm_use_model_mirror)
        self._voxcpm_auto_start.setChecked(settings.voxcpm_auto_start)
        self._voxcpm_voice_prompt.setText(settings.voxcpm_voice_prompt)
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
            voxcpm_endpoint=self._voxcpm_endpoint.text().strip() or AppSettings().voxcpm_endpoint,
            voxcpm_timeout_seconds=self._voxcpm_timeout.value(),
            voxcpm_stream_prebuffer_seconds=self._voxcpm_stream_prebuffer.value(),
            voxcpm_install_root=self._voxcpm_install_root.text().strip() or AppSettings().voxcpm_install_root,
            voxcpm_model_cache_root=self._voxcpm_model_cache_root.text().strip()
            or AppSettings().voxcpm_model_cache_root,
            voxcpm_use_model_mirror=self._voxcpm_use_model_mirror.isChecked(),
            voxcpm_auto_start=self._voxcpm_auto_start.isChecked(),
            voxcpm_voice_prompt=self._voxcpm_voice_prompt.text().strip(),
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

        self._voxcpm_message.setWordWrap(True)
        self._voxcpm_runtime_meta.setWordWrap(True)
        self._tabs.addTab(self._build_learning_tab(), "学习")
        self._tabs.addTab(self._build_display_tab(), "显示")
        self._tabs.addTab(self._build_pronunciation_tab(), "发音")
        self._tabs.addTab(self._build_hotkeys_tab(), "快捷键")
        self._tabs.addTab(self._build_wordbooks_tab(), "词库")
        self._tabs.addTab(self._build_about_tab(), "关于")
        root.addWidget(self._tabs, 1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        buttons_row.addWidget(self._buttons)
        root.addLayout(buttons_row)

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
        settings_form.addRow("安装目录", self._path_row(self._voxcpm_install_root, self._voxcpm_install_browse_button))
        settings_form.addRow(
            "模型目录",
            self._path_row(self._voxcpm_model_cache_root, self._voxcpm_model_browse_button),
        )
        settings_form.addRow(self._voxcpm_use_model_mirror)
        settings_form.addRow(self._voxcpm_auto_start)
        settings_form.addRow("语气提示词", self._voxcpm_voice_prompt)
        service_layout.addLayout(settings_form)

        action_row = QHBoxLayout()
        action_row.addWidget(self._voxcpm_runtime_button)
        action_row.addWidget(self._voxcpm_runtime_download_button)
        action_row.addWidget(self._voxcpm_model_button)
        action_row.addWidget(self._voxcpm_install_button)
        action_row.addWidget(self._voxcpm_start_button)
        action_row.addWidget(self._voxcpm_stop_button)
        action_row.addWidget(self._voxcpm_check_button)
        action_row.addWidget(self._voxcpm_open_log_button)
        action_row.addStretch(1)
        service_layout.addLayout(action_row)
        layout.addWidget(service_group)
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

    def set_voxcpm_download_progress(self, stage: str) -> None:
        self._voxcpm_message.setText(stage)

    def set_voxcpm_status(self, status: object) -> None:
        installed = bool(getattr(status, "installed", False))
        running = bool(getattr(status, "running", False))
        installing = bool(getattr(status, "installing", False))
        message = str(getattr(status, "message", "") or "")
        log_path = getattr(status, "log_path", None)
        runtime_state = str(getattr(status, "runtime_state", "") or "")
        runtime_id = str(getattr(status, "runtime_id", "") or "")
        cuda_tag = str(getattr(status, "cuda_tag", "") or "")
        min_driver_version = str(getattr(status, "min_driver_version", "") or "")
        model_version = str(getattr(status, "model_version", "") or "")

        if installing:
            install_status = "安装中"
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
        self._voxcpm_runtime_button.setEnabled(not installing)
        self._voxcpm_runtime_download_button.setEnabled(not installing)
        self._voxcpm_model_button.setEnabled(not installing)
        self._voxcpm_install_button.setEnabled(not installing)
        self._voxcpm_start_button.setEnabled(installed and not running and not installing)
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
