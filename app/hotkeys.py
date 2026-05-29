from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

MOD_ALT = 0x0001
WM_HOTKEY = 0x0312

VK_CODE_BY_DIGIT = {
    "0": 0x30,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
    "9": 0x39,
}


@dataclass(slots=True)
class RegisteredHotkey:
    hotkey_id: int
    action_name: str
    sequence: str


class _NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, service: "GlobalHotkeyService") -> None:
        super().__init__()
        self._service = service

    def nativeEventFilter(self, event_type: bytes | str, message: int) -> tuple[bool, int]:
        normalized = event_type.decode() if isinstance(event_type, bytes) else event_type
        if normalized not in {"windows_generic_MSG", "windows_dispatcher_MSG"}:
            return False, 0

        msg = ctypes.cast(message, ctypes.POINTER(wintypes.MSG)).contents
        if msg.message != WM_HOTKEY:
            return False, 0

        self._service._dispatch_hotkey(int(msg.wParam))
        return True, 0


class GlobalHotkeyService(QObject):
    """Registers best-effort global hotkeys and reports user intent via signals."""

    pronounce_requested = Signal()
    toggle_details_requested = Signal()
    trigger_now_requested = Signal()
    mark_mastered_requested = Signal()
    availability_changed = Signal(bool)

    DEFAULT_SEQUENCES = {
        "pronounce": "Alt+1",
        "toggle_details": "Alt+2",
        "trigger_now": "Alt+3",
        "mark_mastered": "Alt+4",
    }

    def __init__(
        self,
        app: QApplication | None = None,
        parent: QObject | None = None,
        *,
        sequences: dict[str, str] | None = None,
        on_pronounce: Callable[[], Any] | None = None,
        on_toggle_details: Callable[[], Any] | None = None,
        on_trigger_now: Callable[[], Any] | None = None,
        on_mark_mastered: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._app = app or QApplication.instance()
        self._event_filter: _NativeHotkeyFilter | None = None
        self._user32 = getattr(ctypes, "windll", None)
        self._requested_sequences = dict(self.DEFAULT_SEQUENCES)
        if sequences:
            self._requested_sequences.update(sequences)
        self._registered: dict[int, RegisteredHotkey] = {}
        self._registration_errors: dict[str, str] = {}
        self._started = False

        if on_pronounce is not None:
            self.pronounce_requested.connect(on_pronounce)
        if on_toggle_details is not None:
            self.toggle_details_requested.connect(on_toggle_details)
        if on_trigger_now is not None:
            self.trigger_now_requested.connect(on_trigger_now)
        if on_mark_mastered is not None:
            self.mark_mastered_requested.connect(on_mark_mastered)

    @property
    def is_available(self) -> bool:
        return self._user32 is not None and self._app is not None

    @property
    def registration_errors(self) -> dict[str, str]:
        return dict(self._registration_errors)

    @property
    def registered_hotkeys(self) -> dict[str, str]:
        return {
            hotkey.action_name: hotkey.sequence for hotkey in self._registered.values()
        }

    def start(self) -> None:
        if self._started:
            return

        self._started = True
        self._registered.clear()
        self._registration_errors.clear()

        if not self.is_available:
            self._registration_errors["service"] = "Global hotkeys require a Windows Qt app context."
            self._started = False
            self.availability_changed.emit(False)
            return

        self._event_filter = _NativeHotkeyFilter(self)
        self._app.installNativeEventFilter(self._event_filter)

        for offset, (action_name, sequence) in enumerate(self._requested_sequences.items(), start=1):
            self._register_hotkey(offset, action_name, sequence)

        self.availability_changed.emit(bool(self._registered))

    def stop(self) -> None:
        if not self._started:
            return

        if self._user32 is not None:
            for hotkey_id in list(self._registered):
                self._user32.user32.UnregisterHotKey(None, hotkey_id)

        if self._app is not None and self._event_filter is not None:
            self._app.removeNativeEventFilter(self._event_filter)

        self._registered.clear()
        self._event_filter = None
        self._started = False
        self.availability_changed.emit(False)

    def rebind(self, sequences: dict[str, str]) -> None:
        self._requested_sequences = dict(self.DEFAULT_SEQUENCES)
        self._requested_sequences.update(sequences)
        was_started = self._started
        self.stop()
        if was_started:
            QTimer.singleShot(0, self.start)

    def _register_hotkey(self, hotkey_id: int, action_name: str, sequence: str) -> None:
        parsed = self._parse_sequence(sequence)
        if parsed is None:
            self._registration_errors[action_name] = f"Unsupported hotkey: {sequence!r}"
            return

        modifiers, vk_code = parsed
        ok = bool(self._user32.user32.RegisterHotKey(None, hotkey_id, modifiers, vk_code))
        if not ok:
            self._registration_errors[action_name] = f"RegisterHotKey failed for {sequence!r}"
            return

        self._registered[hotkey_id] = RegisteredHotkey(hotkey_id, action_name, sequence)

    def _dispatch_hotkey(self, hotkey_id: int) -> None:
        hotkey = self._registered.get(hotkey_id)
        if hotkey is None:
            return

        if hotkey.action_name == "pronounce":
            self.pronounce_requested.emit()
        elif hotkey.action_name == "toggle_details":
            self.toggle_details_requested.emit()
        elif hotkey.action_name == "trigger_now":
            self.trigger_now_requested.emit()
        elif hotkey.action_name == "mark_mastered":
            self.mark_mastered_requested.emit()

    @staticmethod
    def _parse_sequence(sequence: str) -> tuple[int, int] | None:
        normalized = sequence.strip().lower().replace(" ", "")
        parts = [part for part in normalized.split("+") if part]
        if len(parts) != 2 or "alt" not in parts:
            return None

        key = parts[0] if parts[1] == "alt" else parts[1]
        vk_code = VK_CODE_BY_DIGIT.get(key)
        if vk_code is None:
            return None

        return MOD_ALT, vk_code
