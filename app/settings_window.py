from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import Accent, AppSettings, DisplayMode, OverlayPosition


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("oh my word settings")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setModal(False)
        self.resize(440, 520)

        self._display_mode = QComboBox(self)
        self._card_position = QComboBox(self)
        self._barrage_position = QComboBox(self)
        self._accent = QComboBox(self)
        self._enabled = QCheckBox("Enable automatic popups", self)
        self._mute = QCheckBox("Mute pronunciation", self)
        self._min_delay = QSpinBox(self)
        self._max_delay = QSpinBox(self)
        self._busy_stop = QSpinBox(self)
        self._popup_duration = QSpinBox(self)
        self._pronounce_hotkey = QLineEdit(self)
        self._toggle_detail_hotkey = QLineEdit(self)
        self._trigger_now_hotkey = QLineEdit(self)
        self._mark_mastered_hotkey = QLineEdit(self)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )

        self._build_ui()
        self.set_settings(settings)

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
        self._busy_stop.setValue(settings.busy_stop_threshold_seconds)
        self._popup_duration.setValue(settings.popup_duration_seconds)
        self._pronounce_hotkey.setText(settings.pronounce_hotkey)
        self._toggle_detail_hotkey.setText(settings.toggle_detail_hotkey)
        self._trigger_now_hotkey.setText(settings.trigger_now_hotkey)
        self._mark_mastered_hotkey.setText(settings.mark_mastered_hotkey)

    def get_settings(self) -> AppSettings:
        return AppSettings(
            enabled=self._enabled.isChecked(),
            display_mode=self._display_mode.currentData(),
            card_position=self._card_position.currentData(),
            barrage_position=self._barrage_position.currentData(),
            min_delay_minutes=self._min_delay.value(),
            max_delay_minutes=self._max_delay.value(),
            busy_stop_threshold_seconds=self._busy_stop.value(),
            popup_duration_seconds=self._popup_duration.value(),
            mute_pronunciation=self._mute.isChecked(),
            accent=self._accent.currentData(),
            pronounce_hotkey=self._pronounce_hotkey.text().strip() or AppSettings().pronounce_hotkey,
            toggle_detail_hotkey=self._toggle_detail_hotkey.text().strip() or AppSettings().toggle_detail_hotkey,
            trigger_now_hotkey=self._trigger_now_hotkey.text().strip() or AppSettings().trigger_now_hotkey,
            mark_mastered_hotkey=self._mark_mastered_hotkey.text().strip() or AppSettings().mark_mastered_hotkey,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        hint = QLabel("Portable settings for the Python rewrite. Save applies immediately.", self)
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        root.addLayout(form)

        for combo, enum_type in (
            (self._display_mode, DisplayMode),
            (self._card_position, OverlayPosition),
            (self._barrage_position, OverlayPosition),
            (self._accent, Accent),
        ):
            for member in enum_type:
                combo.addItem(member.value, member)

        for spin in (self._min_delay, self._max_delay):
            spin.setRange(1, 240)
            spin.setSuffix(" min")

        for spin in (self._busy_stop, self._popup_duration):
            spin.setRange(1, 600)
            spin.setSuffix(" s")

        form.addRow(self._enabled)
        form.addRow(self._mute)
        form.addRow("Display mode", self._display_mode)
        form.addRow("Card position", self._card_position)
        form.addRow("Barrage position", self._barrage_position)
        form.addRow("Accent", self._accent)
        form.addRow("Min delay", self._min_delay)
        form.addRow("Max delay", self._max_delay)
        form.addRow("Busy stop threshold", self._busy_stop)
        form.addRow("Popup duration", self._popup_duration)
        form.addRow("Pronounce hotkey", self._pronounce_hotkey)
        form.addRow("Toggle details hotkey", self._toggle_detail_hotkey)
        form.addRow("Trigger now hotkey", self._trigger_now_hotkey)
        form.addRow("Mark mastered hotkey", self._mark_mastered_hotkey)

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
