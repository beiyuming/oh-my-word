from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import Accent, AppSettings, DisplayMode, OverlayPosition


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

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("oh my word 设置")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setModal(False)
        self.resize(440, 660)

        self._display_mode = QComboBox(self)
        self._card_position = QComboBox(self)
        self._barrage_position = QComboBox(self)
        self._accent = QComboBox(self)
        self._enabled = QCheckBox(self)
        self._mute = QCheckBox(self)
        self._min_delay = QSpinBox(self)
        self._max_delay = QSpinBox(self)
        self._activity_threshold = QSpinBox(self)
        self._activity_weight = QSpinBox(self)
        self._popup_duration = QSpinBox(self)
        self._snooze_minutes = QSpinBox(self)
        self._pronounce_hotkey = HotkeyCaptureButton(self)
        self._toggle_detail_hotkey = HotkeyCaptureButton(self)
        self._trigger_now_hotkey = HotkeyCaptureButton(self)
        self._mark_mastered_hotkey = HotkeyCaptureButton(self)
        self._known_hotkey = HotkeyCaptureButton(self)
        self._unknown_hotkey = HotkeyCaptureButton(self)
        self._dismiss_hotkey = HotkeyCaptureButton(self)
        self._import_wordbook_button = QPushButton("导入词库...", self)
        self._download_wordbook_button = QPushButton("下载推荐考研词库", self)
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
        self._import_wordbook_button.clicked.connect(self.import_wordbook_requested.emit)
        self._download_wordbook_button.clicked.connect(self.download_wordbook_requested.emit)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

    def set_settings(self, settings: AppSettings) -> None:
        self._enabled.setChecked(settings.enabled)
        self._mute.setChecked(settings.mute_pronunciation)
        self._set_enum_value(self._display_mode, settings.display_mode)
        self._set_enum_value(self._card_position, settings.card_position)
        self._set_enum_value(self._barrage_position, settings.barrage_position)
        self._set_enum_value(self._accent, settings.accent)
        self._min_delay.setValue(settings.min_delay_minutes)
        self._max_delay.setValue(settings.max_delay_minutes)
        self._activity_threshold.setValue(settings.activity_threshold_per_minute)
        self._activity_weight.setValue(settings.activity_slowdown_weight)
        self._popup_duration.setValue(settings.popup_duration_seconds)
        self._snooze_minutes.setValue(settings.snooze_minutes)
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
            display_mode=self._display_mode.currentData(),
            card_position=self._card_position.currentData(),
            barrage_position=self._barrage_position.currentData(),
            min_delay_minutes=self._min_delay.value(),
            max_delay_minutes=self._max_delay.value(),
            activity_threshold_per_minute=self._activity_threshold.value(),
            activity_slowdown_weight=self._activity_weight.value(),
            popup_duration_seconds=self._popup_duration.value(),
            snooze_minutes=self._snooze_minutes.value(),
            mute_pronunciation=self._mute.isChecked(),
            accent=self._accent.currentData(),
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

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        root.addLayout(form)

        for member in DisplayMode:
            self._display_mode.addItem(_ENUM_LABELS.get(member, member.value), member)
        for member in OverlayPosition:
            self._card_position.addItem(_ENUM_LABELS.get(member, member.value), member)
            self._barrage_position.addItem(_ENUM_LABELS.get(member, member.value), member)
        for member in Accent:
            self._accent.addItem(_ENUM_LABELS.get(member, member.value), member)

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

        form.addRow(self._enabled)
        form.addRow(self._mute)
        form.addRow("显示方式", self._display_mode)
        form.addRow("卡片位置", self._card_position)
        form.addRow("弹幕位置", self._barrage_position)
        form.addRow("发音口音", self._accent)
        form.addRow("最短间隔", self._min_delay)
        form.addRow("最长间隔", self._max_delay)
        form.addRow("高频操作阈值", self._activity_threshold)
        form.addRow("频率影响权重", self._activity_weight)
        form.addRow("卡片停留时长", self._popup_duration)
        form.addRow("稍后时长", self._snooze_minutes)
        form.addRow("朗读快捷键", self._pronounce_hotkey)
        form.addRow("展开详情快捷键", self._toggle_detail_hotkey)
        form.addRow("立刻弹出快捷键", self._trigger_now_hotkey)
        form.addRow("标记掌握快捷键", self._mark_mastered_hotkey)
        form.addRow("认识快捷键", self._known_hotkey)
        form.addRow("不认识快捷键", self._unknown_hotkey)
        form.addRow("关闭快捷键", self._dismiss_hotkey)
        form.addRow("词库", self._import_wordbook_button)
        form.addRow("", self._download_wordbook_button)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        buttons_row.addWidget(self._buttons)
        root.addLayout(buttons_row)

    @staticmethod
    def _set_enum_value(combo: QComboBox, value: object) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

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
