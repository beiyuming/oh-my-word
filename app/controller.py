from __future__ import annotations

import ctypes
import logging
import random
import sys
from collections import deque
from ctypes import wintypes
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QStyle

from .hotkeys import GlobalHotkeyService
from .models import (
    AppSettings,
    DEFAULT_RECENT_WORDS_LIMIT,
    DisplayMode,
    LearningState,
    WordEntry,
    WordProgress,
)
from .overlays.barrage_popup import BarragePopup
from .overlays.card_popup import CardPopup
from .fsrs_service import ProjectReviewRating
from .scheduler import QtScheduler, SchedulerAction, SchedulerActionKind
from .settings import LearningStateStore, SettingsStore, ensure_storage_layout, setup_app_logger
from .settings_window import SettingsDialog
from .study_store import StudyStore
from .tray import TrayController
from .tts import PronunciationService
from .words import (
    DEFAULT_RECENT_WORDS_WINDOW,
    RECOMMENDED_KAOYAN_LICENSE,
    RECOMMENDED_KAOYAN_SOURCE_PAGE,
    WordCatalog,
    download_recommended_kaoyan_wordbook,
    import_wordbook_file,
    load_word_catalog,
    select_next_word,
)


@dataclass(slots=True)
class AppPaths:
    root_dir: Path
    data_dir: Path
    wordbooks_dir: Path
    storage_dir: Path
    settings_path: Path
    learning_state_path: Path
    study_db_path: Path
    log_path: Path

    @classmethod
    def from_root(cls, root_dir: Path) -> "AppPaths":
        return cls.from_roots(root_dir=root_dir, data_root=root_dir, storage_root=root_dir)

    @classmethod
    def from_runtime(cls) -> "AppPaths":
        if getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            resource_root = Path(getattr(sys, "_MEIPASS", executable_dir)).resolve()
            return cls.from_roots(
                root_dir=executable_dir,
                data_root=resource_root,
                storage_root=executable_dir,
            )

        return cls.from_root(Path(__file__).resolve().parent.parent)

    @classmethod
    def from_roots(cls, *, root_dir: Path, data_root: Path, storage_root: Path) -> "AppPaths":
        data_dir = data_root / "data"
        wordbooks_dir = data_dir / "wordbooks"
        storage_dir = storage_root / "storage"
        return cls(
            root_dir=root_dir,
            data_dir=data_dir,
            wordbooks_dir=wordbooks_dir,
            storage_dir=storage_dir,
            settings_path=storage_dir / "settings.json",
            learning_state_path=storage_dir / "learning_state.json",
            study_db_path=storage_dir / "oh_my_word.sqlite3",
            log_path=storage_dir / "app.log",
        )


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_MOUSEHWHEEL = 0x020E


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


class ActivityMonitor:
    def __init__(self, *, window_seconds: int = 15) -> None:
        self._window_seconds = max(1, window_seconds)
        self._events: deque[float] = deque()
        self._last_mouse_move_at = 0.0
        self._user32 = getattr(ctypes, "windll", None)
        self._keyboard_hook: int | None = None
        self._mouse_hook: int | None = None
        self._keyboard_proc: Any | None = None
        self._mouse_proc: Any | None = None

    def start(self) -> None:
        if self._user32 is None:
            return
        self._configure_win32_api()
        module_handle = self._user32.kernel32.GetModuleHandleW(None)
        self._keyboard_proc = HOOKPROC(self._handle_keyboard_event)
        self._mouse_proc = HOOKPROC(self._handle_mouse_event)
        self._keyboard_hook = int(
            self._user32.user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._keyboard_proc,
                module_handle,
                0,
            )
            or 0
        )
        self._mouse_hook = int(
            self._user32.user32.SetWindowsHookExW(
                WH_MOUSE_LL,
                self._mouse_proc,
                module_handle,
                0,
            )
            or 0
        )

    def stop(self) -> None:
        if self._user32 is None:
            return
        if self._keyboard_hook:
            self._user32.user32.UnhookWindowsHookEx(self._keyboard_hook)
        if self._mouse_hook:
            self._user32.user32.UnhookWindowsHookEx(self._mouse_hook)
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_proc = None
        self._mouse_proc = None

    def get_activity_events_per_minute(self) -> float:
        self._prune_events()
        return len(self._events) * 60.0 / self._window_seconds

    def _handle_keyboard_event(self, code: int, w_param: int, l_param: int) -> int:
        if code >= 0 and int(w_param) in (WM_KEYDOWN, WM_SYSKEYDOWN):
            self._record_event()
        return self._call_next_hook(self._keyboard_hook, code, w_param, l_param)

    def _handle_mouse_event(self, code: int, w_param: int, l_param: int) -> int:
        if code >= 0:
            message = int(w_param)
            now = monotonic()
            if message == WM_MOUSEMOVE:
                if now - self._last_mouse_move_at >= 0.35:
                    self._last_mouse_move_at = now
                    self._record_event(now)
            elif message in (
                WM_LBUTTONDOWN,
                WM_RBUTTONDOWN,
                WM_MBUTTONDOWN,
                WM_XBUTTONDOWN,
                WM_MOUSEWHEEL,
                WM_MOUSEHWHEEL,
            ):
                self._record_event(now)
        return self._call_next_hook(self._mouse_hook, code, w_param, l_param)

    def _record_event(self, event_time: float | None = None) -> None:
        self._events.append(event_time or monotonic())
        self._prune_events()

    def _prune_events(self) -> None:
        cutoff = monotonic() - self._window_seconds
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

    def _call_next_hook(self, hook: int | None, code: int, w_param: int, l_param: int) -> int:
        if self._user32 is None:
            return 0
        return int(self._user32.user32.CallNextHookEx(hook, code, w_param, l_param))

    def _configure_win32_api(self) -> None:
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


class AppController(QObject):
    """Coordinates settings, scheduling, overlays, tray, hotkeys, and TTS."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._paths = AppPaths.from_runtime()
        self._root_dir = self._paths.root_dir
        self._rng = random.Random()
        self._activity_monitor = ActivityMonitor()
        self._app_icon = self._build_app_icon()

        self.settings = AppSettings()
        self.learning_state = LearningState()
        self.current_word: WordEntry | None = None
        self.settings_window: SettingsDialog | None = None

        self.logger: logging.Logger | None = None
        self.settings_store: SettingsStore | None = None
        self.learning_state_store: LearningStateStore | None = None
        self.study_store: StudyStore | None = None
        self.catalog = WordCatalog(words=(), by_word={})

        self.scheduler: QtScheduler[WordEntry] | None = None
        self.tray: TrayController | None = None
        self.hotkeys: GlobalHotkeyService | None = None
        self.tts: PronunciationService | None = None
        self.card_popup: CardPopup | None = None
        self.barrage_popup: BarragePopup | None = None

    @property
    def paths(self) -> AppPaths:
        return self._paths

    def initialize(self) -> None:
        ensure_storage_layout(self._paths)
        self._paths.wordbooks_dir.mkdir(parents=True, exist_ok=True)
        first_launch = not self._paths.settings_path.exists()

        self.logger = setup_app_logger(self._paths)
        self.settings_store = SettingsStore(self._paths, self.logger)
        self.learning_state_store = LearningStateStore(self._paths, self.logger)
        self.study_store = StudyStore(self._paths.study_db_path, logger=self.logger)
        self.study_store.initialize()
        self.study_store.import_legacy_learning_state(self._paths.learning_state_path)
        self._activity_monitor.start()

        self.settings = self.settings_store.load()
        self.learning_state = self.learning_state_store.load()

        catalog_result = load_word_catalog(self._paths.wordbooks_dir)
        self.catalog = catalog_result.catalog
        for issue in catalog_result.issues:
            self._log_warning("%s: %s", issue.source, issue.message)

        self.card_popup = CardPopup()
        self.barrage_popup = BarragePopup()
        self._wire_overlay_signals()

        self.tray = TrayController(
            icon=self._app_icon,
            on_toggle_enabled=self._on_toggle_enabled_requested,
            on_trigger_now=self._on_trigger_now_requested,
            on_switch_display_mode=self._on_switch_display_mode_requested,
            on_open_settings=self.show_settings_window,
            on_snooze_app=self.snooze_app_for_default_duration,
            on_exit=self.exit,
        )
        self._app.setWindowIcon(self._app_icon)
        self.tray.set_enabled(self.settings.enabled)
        self.tray.set_display_mode(self.settings.display_mode)
        self.tray.show()

        self.hotkeys = GlobalHotkeyService(
            self._app,
            sequences=self._hotkey_sequences(),
            on_pronounce=self.pronounce_current_word,
            on_toggle_details=self.toggle_details,
            on_trigger_now=self._on_trigger_now_requested,
            on_mark_mastered=self.mark_current_word_mastered,
            on_known=lambda: self.review_visible_popup(known=True),
            on_unknown=lambda: self.review_visible_popup(known=False),
            on_dismiss=self.dismiss_visible_popup,
        )
        self.hotkeys.start()
        self._notify_hotkey_registration_errors()

        self.tts = PronunciationService(accent=self.settings.accent, on_error=self._log_warning_text)

        self.scheduler = QtScheduler(
            settings_provider=lambda: self.settings,
            activity_rate_provider=self._activity_monitor.get_activity_events_per_minute,
            emit_action=self._handle_scheduler_action,
        )
        if self.settings.enabled:
            self.scheduler.start()

        if catalog_result.recovered_with_default and self.tray is not None:
            self.tray.show_message("oh my word", "已恢复默认考研词书。")

        if first_launch or not self._tray_ready():
            self.show_settings_window()

    def show_settings_window(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsDialog(self.settings)
            self.settings_window.accepted.connect(self._save_settings_from_dialog)
            self.settings_window.import_wordbook_requested.connect(self.import_wordbook)
            self.settings_window.download_wordbook_requested.connect(self.download_recommended_wordbook)
            self.settings_window.finished.connect(self._on_settings_window_finished)
        else:
            self.settings_window.set_settings(self.settings)

        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def import_wordbook(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self.settings_window,
            "导入词库",
            str(self._paths.root_dir),
            "词库文件 (*.json *.csv)",
        )
        if not source:
            return

        try:
            result = import_wordbook_file(Path(source), self._paths.wordbooks_dir)
            catalog_result = load_word_catalog(self._paths.wordbooks_dir)
        except ValueError as exc:
            QMessageBox.warning(self.settings_window, "导入失败", str(exc))
            return

        self.catalog = catalog_result.catalog
        for issue in catalog_result.issues:
            self._log_warning("%s: %s", issue.source, issue.message)
        if self.tray is not None:
            self.tray.show_message(
                "oh my word",
                f"已导入 {result.imported_count} 个单词：{result.path.name}",
            )

    def download_recommended_wordbook(self) -> None:
        confirmation = QMessageBox.question(
            self.settings_window,
            "下载推荐考研词库",
            "将从 exam-data/NETEMVocabulary 下载 2024 考研英语（一）大纲词汇，并写入本地 data/wordbooks/kaoyan_full.json。\n\n"
            f"来源：{RECOMMENDED_KAOYAN_SOURCE_PAGE}\n"
            f"词库许可：{RECOMMENDED_KAOYAN_LICENSE}\n\n"
            "请确认你接受该第三方词库的许可和用途限制。",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        try:
            result = download_recommended_kaoyan_wordbook(self._paths.wordbooks_dir)
            catalog_result = load_word_catalog(self._paths.wordbooks_dir)
        except ValueError as exc:
            QMessageBox.warning(self.settings_window, "下载失败", str(exc))
            return

        self.catalog = catalog_result.catalog
        for issue in catalog_result.issues:
            self._log_warning("%s: %s", issue.source, issue.message)
        if self.tray is not None:
            self.tray.show_message(
                "oh my word",
                f"已下载推荐考研词库，共 {result.imported_count} 个单词。",
            )

    def pronounce_current_word(self) -> None:
        if self.current_word is None:
            return
        self.pronounce_text(_pronunciation_text(self.current_word))

    def pronounce_text(self, text: str) -> None:
        if self.current_word is None or self.settings.mute_pronunciation or self.tts is None:
            return
        if self.tts.speak(text, accent=self.settings.accent):
            if self.study_store is not None:
                self.study_store.record_word_pronounced(
                    self.current_word.word,
                    pronounced_at=datetime.now(UTC),
                )
            else:
                self._update_progress(
                    self.current_word.word,
                    lambda progress: replace(progress, last_pronounced_at=_now_iso()),
                )

    def toggle_details(self) -> None:
        if self.current_word is None:
            return
        if self.card_popup is not None and self.card_popup.isVisible():
            self.card_popup.set_details_expanded(not self.card_popup.is_details_expanded())
        elif self.barrage_popup is not None and self.barrage_popup.isVisible():
            self.barrage_popup.set_details_expanded(not self.barrage_popup.is_details_expanded())
        else:
            return
        if self.study_store is not None:
            self.study_store.record_word_expanded(self.current_word.word, expanded_at=datetime.now(UTC))
        else:
            self._update_progress(
                self.current_word.word,
                lambda progress: replace(progress, last_expanded_at=_now_iso()),
            )

    def mark_current_word_mastered(self) -> None:
        if self.current_word is None:
            return
        word_key = self.current_word.word
        if self.study_store is not None:
            self.study_store.mark_word_mastered(word_key)
        else:
            self._update_progress(word_key, lambda progress: replace(progress, mastered=True))
        self._close_active_popup()
        if self.tray is not None:
            self.tray.show_message("oh my word", f"已将「{word_key}」标记为已掌握。")

    def exit(self) -> None:
        if self.scheduler is not None:
            self.scheduler.dispose()
        if self.hotkeys is not None:
            self.hotkeys.stop()
        self._activity_monitor.stop()
        if self.tray is not None:
            self.tray.destroy()
        self._close_active_popup()
        self._app.quit()

    def _handle_scheduler_action(self, action: SchedulerAction[WordEntry]) -> None:
        if action.kind is SchedulerActionKind.SHOW_WORD and action.word is not None:
            if self._has_active_popup():
                if action.reason == "manual":
                    self._close_active_popup()
                    self._show_word(action.word)
                    return
                if self.scheduler is not None:
                    self.scheduler.enqueue_word(action.word)
                return
            self._show_word(action.word)
            return

        if action.kind is SchedulerActionKind.REQUEST_FRESH_WORD:
            self._request_fresh_word(manual=(action.reason == "manual"))

    def _request_fresh_word(self, *, manual: bool) -> None:
        if self.study_store is not None:
            result = self.study_store.select_next_word(
                self.catalog.words,
                now=datetime.now(UTC),
                recent_window_size=DEFAULT_RECENT_WORDS_WINDOW,
            )
        else:
            result = select_next_word(
                self.catalog,
                self.learning_state,
                recent_window_size=DEFAULT_RECENT_WORDS_WINDOW,
                rng=self._rng,
            )
        if result.word is None:
            if (
                result.should_pause
                and self.scheduler is not None
                and not manual
                and result.notice_key == "all_mastered"
            ):
                self.scheduler.pause()
            if self.tray is not None and result.notice_key == "all_mastered":
                self.tray.show_message("oh my word", "未掌握的单词已经学完了。")
            return

        if self._has_active_popup() and not manual:
            if self.scheduler is not None:
                decision = self.scheduler.enqueue_word(result.word)
                if not decision.accepted:
                    self._log_info("Queued word already occupied; keeping first queued item.")
            return

        if self._has_active_popup():
            self._close_active_popup()

        self._show_word(result.word)

    def _show_word(self, word: WordEntry) -> None:
        self.current_word = word
        popup_duration_ms = self.settings.popup_duration_seconds * 1000
        if self.settings.display_mode is DisplayMode.CARD:
            assert self.card_popup is not None
            self.card_popup.show_popup(
                word,
                position=self.settings.card_position,
                auto_hide_ms=popup_duration_ms,
            )
        else:
            assert self.barrage_popup is not None
            self.barrage_popup.show_popup(
                word,
                position=self.settings.barrage_position,
            )

        if self.study_store is not None:
            self.study_store.record_word_shown(word.word, shown_at=datetime.now(UTC))
        else:
            self._update_progress(
                word.word,
                lambda progress: replace(
                    progress,
                    show_count=progress.show_count + 1,
                    last_shown_at=_now_iso(),
                ),
                update_recent=True,
            )

    def _save_settings_from_dialog(self) -> None:
        if self.settings_window is None or self.settings_store is None:
            return
        self.settings = self.settings_store.save(self.settings_window.get_settings())
        self._apply_settings()

    def _apply_settings(self) -> None:
        if self.tray is not None:
            self.tray.set_enabled(self.settings.enabled)
            self.tray.set_display_mode(self.settings.display_mode)

        if self.hotkeys is not None:
            self.hotkeys.rebind(self._hotkey_sequences())
            self._notify_hotkey_registration_errors()

        if self.tts is not None:
            self.tts.set_accent(self.settings.accent)

        if self.scheduler is not None:
            if self.settings.enabled:
                self.scheduler.start()
            else:
                self.scheduler.pause()
                self._close_active_popup()

    def _wire_overlay_signals(self) -> None:
        assert self.card_popup is not None and self.barrage_popup is not None
        self.card_popup.pronounce.connect(self.pronounce_text)
        self.card_popup.mark_mastered.connect(lambda _: self.mark_current_word_mastered())
        self.card_popup.reviewed.connect(lambda _, known: self.review_current_word(known=known))
        self.card_popup.snoozed.connect(lambda _: self.snooze_visible_popup())
        self.card_popup.dismissed.connect(self._on_popup_dismissed)
        self.card_popup.closed.connect(self._on_popup_closed)
        self.barrage_popup.pronounce.connect(self.pronounce_text)
        self.barrage_popup.mark_mastered.connect(lambda _: self.mark_current_word_mastered())
        self.barrage_popup.reviewed.connect(lambda _, known: self.review_current_word(known=known))
        self.barrage_popup.snoozed.connect(lambda _: self.snooze_visible_popup())
        self.barrage_popup.dismissed.connect(self._on_popup_dismissed)
        self.barrage_popup.closed.connect(self._on_popup_closed)

    def review_current_word(self, *, known: bool) -> None:
        if self.current_word is None:
            return
        word = self.current_word
        if self.study_store is not None:
            self.study_store.review_word(
                word.word,
                ProjectReviewRating.KNOWN if known else ProjectReviewRating.UNKNOWN,
                reviewed_at=datetime.now(UTC),
            )
        else:
            from .review import apply_review_result

            self._update_progress(
                word.word,
                lambda progress: apply_review_result(progress, known=known),
            )
        self._close_active_popup()

    def review_visible_popup(self, *, known: bool) -> None:
        if self.current_word is None or not self._has_active_popup():
            return
        self.review_current_word(known=known)

    def dismiss_visible_popup(self) -> None:
        if self.current_word is None or not self._has_active_popup():
            return
        self._close_active_popup()

    def snooze_visible_popup(self) -> None:
        if self.current_word is None or not self._has_active_popup() or self.study_store is None:
            return
        until = datetime.now(UTC) + timedelta(minutes=self.settings.snooze_minutes)
        self.study_store.snooze_word(self.current_word.word, until=until)
        self._close_active_popup()

    def snooze_app_for_default_duration(self) -> None:
        if self.study_store is None:
            return
        until = datetime.now(UTC) + timedelta(minutes=self.settings.snooze_minutes)
        self.study_store.snooze_app(until=until)
        self._close_active_popup()
        if self.tray is not None:
            self.tray.show_message("oh my word", f"已暂停 {self.settings.snooze_minutes} 分钟。")

    def _hotkey_sequences(self) -> dict[str, str]:
        return {
            "pronounce": self.settings.pronounce_hotkey,
            "toggle_details": self.settings.toggle_detail_hotkey,
            "trigger_now": self.settings.trigger_now_hotkey,
            "mark_mastered": self.settings.mark_mastered_hotkey,
            "known": self.settings.known_hotkey,
            "unknown": self.settings.unknown_hotkey,
            "dismiss": self.settings.dismiss_hotkey,
        }

    def _on_toggle_enabled_requested(self, enabled: bool) -> None:
        self.settings.enabled = enabled
        if self.settings_store is not None:
            self.settings = self.settings_store.save(self.settings)
        self._apply_settings()

    def _on_switch_display_mode_requested(self) -> None:
        self.settings.display_mode = (
            DisplayMode.BARRAGE if self.settings.display_mode is DisplayMode.CARD else DisplayMode.CARD
        )
        if self.settings_store is not None:
            self.settings = self.settings_store.save(self.settings)
        self._apply_settings()

    def _on_trigger_now_requested(self) -> None:
        if self.scheduler is not None:
            self.scheduler.manual_request()
            self.scheduler.reset()
        else:
            self._request_fresh_word(manual=True)

    def _on_popup_closed(self) -> None:
        self.current_word = None

    def _on_popup_dismissed(self) -> None:
        if self.current_word is not None and self.scheduler is not None:
            self.scheduler.enqueue_word_front(self.current_word)

    def _on_settings_window_finished(self, _: int) -> None:
        self.settings_window = None

    def _has_active_popup(self) -> bool:
        return (self.card_popup is not None and self.card_popup.isVisible()) or (
            self.barrage_popup is not None and self.barrage_popup.isVisible()
        )

    def _close_active_popup(self) -> None:
        if self.card_popup is not None and self.card_popup.isVisible():
            self.card_popup.close()
        if self.barrage_popup is not None and self.barrage_popup.isVisible():
            self.barrage_popup.close()
        self.current_word = None

    def _update_progress(
        self,
        word_key: str,
        updater: Any,
        *,
        update_recent: bool = False,
    ) -> None:
        current = self.learning_state.progress.get(word_key, WordProgress())
        self.learning_state.progress[word_key] = updater(current)
        if update_recent:
            self.learning_state.recent_words.append(word_key)
            self.learning_state.recent_words = self.learning_state.recent_words[-DEFAULT_RECENT_WORDS_LIMIT:]
        if self.learning_state_store is not None:
            self.learning_state = self.learning_state_store.save(self.learning_state)

    def _log_info(self, message: str, *args: object) -> None:
        if self.logger is not None:
            self.logger.info(message, *args)

    def _log_warning(self, message: str, *args: object) -> None:
        if self.logger is not None:
            self.logger.warning(message, *args)

    def _log_warning_text(self, message: str) -> None:
        self._log_warning("%s", message)

    def _notify_hotkey_registration_errors(self) -> None:
        if self.hotkeys is None:
            return

        errors = self.hotkeys.registration_errors
        if not errors:
            return

        action_labels = {
            "pronounce": "朗读",
            "toggle_details": "展开详情",
            "trigger_now": "立刻弹出",
            "mark_mastered": "标记掌握",
            "known": "认识",
            "unknown": "不认识",
            "dismiss": "关闭",
            "service": "快捷键服务",
        }
        details = "；".join(
            f"{action_labels.get(action_name, action_name)}：{message}"
            for action_name, message in errors.items()
        )
        self._log_warning("Hotkey registration failed: %s", details)
        if self.tray is not None:
            self.tray.show_message(
                "oh my word",
                f"有快捷键没有启用，可能被其他软件占用或格式不支持。{details}",
            )

    def show_fatal_error(self, title: str, message: str) -> None:
        QMessageBox.critical(None, title, message)

    def _build_app_icon(self) -> QIcon:
        style = self._app.style()
        for pixmap in (
            QStyle.StandardPixmap.SP_ComputerIcon,
            QStyle.StandardPixmap.SP_FileDialogInfoView,
            QStyle.StandardPixmap.SP_DesktopIcon,
        ):
            icon = style.standardIcon(pixmap)
            if not icon.isNull():
                return icon
        return QIcon()

    def _tray_ready(self) -> bool:
        return (
            self.tray is not None
            and self.tray.tray_icon.isSystemTrayAvailable()
            and not self.tray.tray_icon.icon().isNull()
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _pronunciation_text(entry: WordEntry) -> str:
    if entry.example_sentence and entry.example_sentence.strip() and entry.example_sentence.casefold() != entry.word.casefold():
        return f"{entry.word}. {entry.example_sentence.strip()}"
    return entry.word
