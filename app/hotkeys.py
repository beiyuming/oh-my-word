from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QWidget

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C

MODIFIER_ALIASES = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
    "meta": MOD_WIN,
}

VK_CODE_BY_KEY = {
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
VK_CODE_BY_KEY.update({chr(code): code for code in range(ord("a"), ord("z") + 1)})
VK_CODE_BY_KEY.update({f"f{index}": 0x70 + index - 1 for index in range(1, 25)})


@dataclass(slots=True)
class RegisteredHotkey:
    hotkey_id: int
    action_name: str
    sequence: str
    modifiers: int
    vk_code: int


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


HOOKPROC = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    ctypes.c_long,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class _NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, service: "GlobalHotkeyService") -> None:
        super().__init__()
        self._service = service

    def nativeEventFilter(self, event_type: bytes | str, message: int) -> tuple[bool, int]:
        normalized = event_type.decode() if isinstance(event_type, bytes) else event_type
        if normalized not in {"windows_generic_MSG", "windows_dispatcher_MSG"}:
            return False, 0

        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError, OSError):
            return False, 0

        if msg.message != WM_HOTKEY:
            return False, 0

        self._service._dispatch_hotkey(int(msg.wParam))
        return True, 0


class _HotkeyMessageWindow(QWidget):
    def __init__(self, service: "GlobalHotkeyService") -> None:
        super().__init__(None)
        self._service = service
        self.setWindowTitle("oh-my-word-hotkeys")
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)

    def nativeEvent(self, event_type: bytes | str, message: int) -> tuple[bool, int]:
        normalized = event_type.decode() if isinstance(event_type, bytes) else event_type
        if normalized not in {"windows_generic_MSG", "windows_dispatcher_MSG"}:
            return False, 0

        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError, OSError):
            return False, 0

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
        "pronounce": "Ctrl+Alt+1",
        "toggle_details": "Ctrl+Alt+2",
        "trigger_now": "Ctrl+Alt+3",
        "mark_mastered": "Ctrl+Alt+4",
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
        self._message_window: _HotkeyMessageWindow | None = None
        self._hotkey_hwnd: int | None = None
        self._keyboard_hook: int | None = None
        self._keyboard_proc: Any | None = None
        self._pressed_modifiers = 0
        self._active_hotkeys: set[int] = set()
        self._user32 = getattr(ctypes, "windll", None)
        self._configure_win32_api()
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
            self._registration_errors["service"] = "需要 Windows 的 Qt 应用环境。"
            self._started = False
            self.availability_changed.emit(False)
            return

        self._event_filter = _NativeHotkeyFilter(self)
        self._app.installNativeEventFilter(self._event_filter)
        self._message_window = _HotkeyMessageWindow(self)
        self._hotkey_hwnd = int(self._message_window.winId())
        self._install_keyboard_hook()

        for offset, (action_name, sequence) in enumerate(self._requested_sequences.items(), start=1):
            self._register_hotkey(offset, action_name, sequence)

        self.availability_changed.emit(bool(self._registered))

    def stop(self) -> None:
        if not self._started:
            return

        if self._user32 is not None:
            for hotkey_id in list(self._registered):
                self._user32.user32.UnregisterHotKey(self._hotkey_hwnd, hotkey_id)
            if self._keyboard_hook is not None:
                self._user32.user32.UnhookWindowsHookEx(self._keyboard_hook)

        if self._app is not None and self._event_filter is not None:
            self._app.removeNativeEventFilter(self._event_filter)

        self._registered.clear()
        self._pressed_modifiers = 0
        self._active_hotkeys.clear()
        self._keyboard_hook = None
        self._keyboard_proc = None
        self._event_filter = None
        if self._message_window is not None:
            self._message_window.deleteLater()
        self._message_window = None
        self._hotkey_hwnd = None
        self._started = False
        self.availability_changed.emit(False)

    def rebind(self, sequences: dict[str, str]) -> None:
        self._requested_sequences = dict(self.DEFAULT_SEQUENCES)
        self._requested_sequences.update(sequences)
        was_started = self._started
        self.stop()
        if was_started:
            self.start()

    def _register_hotkey(self, hotkey_id: int, action_name: str, sequence: str) -> None:
        parsed = self._parse_sequence(sequence)
        if parsed is None:
            self._registration_errors[action_name] = f"不支持这个格式：{sequence}"
            return

        modifiers, vk_code = parsed
        if self._keyboard_hook is None:
            ok = bool(
                self._user32.user32.RegisterHotKey(
                    self._hotkey_hwnd,
                    hotkey_id,
                    modifiers | MOD_NOREPEAT,
                    vk_code,
                )
            )
            if not ok:
                error_code = self._user32.kernel32.GetLastError()
                self._registration_errors[action_name] = (
                    f"{sequence} 注册失败，可能被占用（Win32 {error_code}）"
                )
                return

        self._registered[hotkey_id] = RegisteredHotkey(
            hotkey_id,
            action_name,
            sequence,
            modifiers,
            vk_code,
        )

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

    def _install_keyboard_hook(self) -> None:
        if self._user32 is None:
            return

        self._keyboard_proc = HOOKPROC(self._handle_keyboard_event)
        module_handle = self._user32.kernel32.GetModuleHandleW(None)
        hook = self._user32.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._keyboard_proc,
            module_handle,
            0,
        )
        if not hook:
            error_code = self._user32.kernel32.GetLastError()
            self._registration_errors["service"] = f"键盘监听启动失败（Win32 {error_code}）"
            self._keyboard_proc = None
            return
        self._keyboard_hook = int(hook)

    def _handle_keyboard_event(self, code: int, w_param: int, l_param: int) -> int:
        if code < 0:
            return self._call_next_keyboard_hook(code, w_param, l_param)

        event = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk_code = int(event.vkCode)
        if int(w_param) in (WM_KEYDOWN, WM_SYSKEYDOWN):
            self._handle_key_down(vk_code)
        elif int(w_param) in (WM_KEYUP, WM_SYSKEYUP):
            self._handle_key_up(vk_code)
        return self._call_next_keyboard_hook(code, w_param, l_param)

    def _call_next_keyboard_hook(self, code: int, w_param: int, l_param: int) -> int:
        if self._user32 is None:
            return 0
        return int(self._user32.user32.CallNextHookEx(self._keyboard_hook, code, w_param, l_param))

    def _handle_key_down(self, vk_code: int) -> None:
        modifier = self._modifier_for_vk(vk_code)
        if modifier is not None:
            self._pressed_modifiers |= modifier
            return

        for hotkey in self._registered.values():
            if hotkey.vk_code != vk_code or hotkey.modifiers != self._pressed_modifiers:
                continue
            if hotkey.hotkey_id in self._active_hotkeys:
                return
            self._active_hotkeys.add(hotkey.hotkey_id)
            QTimer.singleShot(0, lambda hotkey_id=hotkey.hotkey_id: self._dispatch_hotkey(hotkey_id))
            return

    def _handle_key_up(self, vk_code: int) -> None:
        modifier = self._modifier_for_vk(vk_code)
        if modifier is not None:
            self._pressed_modifiers &= ~modifier
            self._active_hotkeys.clear()
            return

        for hotkey in self._registered.values():
            if hotkey.vk_code == vk_code:
                self._active_hotkeys.discard(hotkey.hotkey_id)

    @staticmethod
    def _modifier_for_vk(vk_code: int) -> int | None:
        if vk_code in (VK_CONTROL, 0xA2, 0xA3):
            return MOD_CONTROL
        if vk_code in (VK_SHIFT, 0xA0, 0xA1):
            return MOD_SHIFT
        if vk_code in (VK_MENU, 0xA4, 0xA5):
            return MOD_ALT
        if vk_code in (VK_LWIN, VK_RWIN):
            return MOD_WIN
        return None

    def _configure_win32_api(self) -> None:
        if self._user32 is None:
            return

        self._user32.user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        self._user32.user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.user32.UnregisterHotKey.restype = wintypes.BOOL
        self._user32.user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        ]
        self._user32.user32.SetWindowsHookExW.restype = wintypes.HHOOK
        self._user32.user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        self._user32.user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._user32.user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._user32.user32.CallNextHookEx.restype = ctypes.c_long
        self._user32.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self._user32.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self._user32.kernel32.GetLastError.argtypes = []
        self._user32.kernel32.GetLastError.restype = wintypes.DWORD

    @staticmethod
    def _parse_sequence(sequence: str) -> tuple[int, int] | None:
        normalized = sequence.strip().lower().replace(" ", "")
        parts = [part for part in normalized.split("+") if part]
        if len(parts) < 2:
            return None

        modifiers = 0
        key = ""
        for part in parts:
            modifier = MODIFIER_ALIASES.get(part)
            if modifier is not None:
                modifiers |= modifier
            elif not key:
                key = part
            else:
                return None

        vk_code = VK_CODE_BY_KEY.get(key)
        if vk_code is None:
            return None

        if modifiers == 0 and not key.startswith("f"):
            return None

        return modifiers, vk_code
