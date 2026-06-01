from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from .models import DisplayMode


_DISPLAY_MODE_LABELS = {
    DisplayMode.CARD: "卡片",
    DisplayMode.BARRAGE: "弹幕",
}


class TrayController(QObject):
    """Owns the system tray icon and emits user intent back to the controller."""

    toggle_enabled_requested = Signal(bool)
    trigger_now_requested = Signal()
    switch_display_mode_requested = Signal()
    open_settings_requested = Signal()
    exit_requested = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        icon: QIcon | None = None,
        tooltip: str = "oh my word",
        on_toggle_enabled: Callable[[bool], Any] | None = None,
        on_trigger_now: Callable[[], Any] | None = None,
        on_switch_display_mode: Callable[[], Any] | None = None,
        on_open_settings: Callable[[], Any] | None = None,
        on_exit: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._tray_icon = QSystemTrayIcon(icon or QIcon(), self)
        self._tray_icon.setToolTip(tooltip)

        self._menu = QMenu()
        self._toggle_enabled_action = QAction(self)
        self._toggle_enabled_action.setCheckable(True)
        self._trigger_now_action = QAction("立刻弹出一个", self)
        self._switch_display_mode_action = QAction(self)
        self._open_settings_action = QAction("打开设置", self)
        self._exit_action = QAction("退出", self)

        self._menu.addAction(self._toggle_enabled_action)
        self._menu.addAction(self._trigger_now_action)
        self._menu.addAction(self._switch_display_mode_action)
        self._menu.addSeparator()
        self._menu.addAction(self._open_settings_action)
        self._menu.addAction(self._exit_action)
        self._tray_icon.setContextMenu(self._menu)

        self._enabled = True
        self._display_mode_label = "未知"

        self._toggle_enabled_action.toggled.connect(self._emit_toggle_enabled_requested)
        self._trigger_now_action.triggered.connect(self.trigger_now_requested.emit)
        self._switch_display_mode_action.triggered.connect(self.switch_display_mode_requested.emit)
        self._open_settings_action.triggered.connect(self.open_settings_requested.emit)
        self._exit_action.triggered.connect(self.exit_requested.emit)
        self._tray_icon.activated.connect(self._handle_activation)

        if on_toggle_enabled is not None:
            self.toggle_enabled_requested.connect(on_toggle_enabled)
        if on_trigger_now is not None:
            self.trigger_now_requested.connect(on_trigger_now)
        if on_switch_display_mode is not None:
            self.switch_display_mode_requested.connect(on_switch_display_mode)
        if on_open_settings is not None:
            self.open_settings_requested.connect(on_open_settings)
        if on_exit is not None:
            self.exit_requested.connect(on_exit)

        self._refresh_labels()
        self._refresh_tooltip()

    @property
    def tray_icon(self) -> QSystemTrayIcon:
        return self._tray_icon

    def show(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon.show()

    def hide(self) -> None:
        self._tray_icon.hide()

    def destroy(self) -> None:
        self.hide()
        self._menu.deleteLater()
        self._tray_icon.deleteLater()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        blocked = self._toggle_enabled_action.blockSignals(True)
        self._toggle_enabled_action.setChecked(self._enabled)
        self._toggle_enabled_action.blockSignals(blocked)
        self._refresh_labels()
        self._refresh_tooltip()

    def set_display_mode(self, display_mode: Any) -> None:
        self._display_mode_label = self._format_enum_value(display_mode)
        self._refresh_labels()
        self._refresh_tooltip()

    def set_icon(self, icon: QIcon) -> None:
        self._tray_icon.setIcon(icon)

    def set_tooltip(self, tooltip: str) -> None:
        self._tray_icon.setToolTip(tooltip)

    def show_message(
        self,
        title: str,
        message: str,
        *,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        timeout_ms: int = 3000,
    ) -> None:
        if self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(title, message, icon, timeout_ms)

    def focus_settings_window(self, widget: QWidget | None) -> None:
        if widget is None:
            return
        widget.show()
        widget.raise_()
        widget.activateWindow()

    def _emit_toggle_enabled_requested(self, checked: bool) -> None:
        self._enabled = bool(checked)
        self._refresh_labels()
        self._refresh_tooltip()
        self.toggle_enabled_requested.emit(self._enabled)

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason is QSystemTrayIcon.ActivationReason.Trigger:
            self.trigger_now_requested.emit()

    def _refresh_labels(self) -> None:
        self._toggle_enabled_action.setText(
            "自动学习：已开启（点击暂停）" if self._enabled else "自动学习：已暂停（点击继续）"
        )
        self._switch_display_mode_action.setText(
            f"切换显示方式（当前：{self._display_mode_label}）"
        )

    def _refresh_tooltip(self) -> None:
        state = "学习中" if self._enabled else "已暂停"
        self._tray_icon.setToolTip(f"oh my word | {state} | {self._display_mode_label}")

    @staticmethod
    def _format_enum_value(value: Any) -> str:
        if value is None:
            return "未知"
        if value in _DISPLAY_MODE_LABELS:
            return _DISPLAY_MODE_LABELS[value]
        name = getattr(value, "name", None)
        raw = name if isinstance(name, str) and name else str(value)
        return raw.replace("_", " ")
