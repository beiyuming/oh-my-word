from __future__ import annotations

import ctypes
import logging
import random
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QStyle

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
from .scheduler import QtScheduler, SchedulerAction, SchedulerActionKind
from .settings import LearningStateStore, SettingsStore, ensure_storage_layout, setup_app_logger
from .settings_window import SettingsDialog
from .tray import TrayController
from .tts import PronunciationService
from .words import DEFAULT_RECENT_WORDS_WINDOW, WordCatalog, load_word_catalog, select_next_word


@dataclass(slots=True)
class AppPaths:
    root_dir: Path
    data_dir: Path
    wordbooks_dir: Path
    storage_dir: Path
    settings_path: Path
    learning_state_path: Path
    log_path: Path

    @classmethod
    def from_root(cls, root_dir: Path) -> "AppPaths":
        data_dir = root_dir / "data"
        wordbooks_dir = data_dir / "wordbooks"
        storage_dir = root_dir / "storage"
        return cls(
            root_dir=root_dir,
            data_dir=data_dir,
            wordbooks_dir=wordbooks_dir,
            storage_dir=storage_dir,
            settings_path=storage_dir / "settings.json",
            learning_state_path=storage_dir / "learning_state.json",
            log_path=storage_dir / "app.log",
        )


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class IdleMonitor:
    def get_idle_seconds(self) -> float:
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not user32.GetLastInputInfo(ctypes.byref(info)):
                return 9999.0
            elapsed_ms = kernel32.GetTickCount() - info.dwTime
            return max(0.0, elapsed_ms / 1000.0)
        except Exception:
            return 9999.0


class AppController(QObject):
    """Coordinates settings, scheduling, overlays, tray, hotkeys, and TTS."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._root_dir = Path(__file__).resolve().parent.parent
        self._paths = AppPaths.from_root(self._root_dir)
        self._rng = random.Random()
        self._idle_monitor = IdleMonitor()
        self._app_icon = self._build_app_icon()

        self.settings = AppSettings()
        self.learning_state = LearningState()
        self.current_word: WordEntry | None = None
        self.settings_window: SettingsDialog | None = None

        self.logger: logging.Logger | None = None
        self.settings_store: SettingsStore | None = None
        self.learning_state_store: LearningStateStore | None = None
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
        )
        self.hotkeys.start()

        self.tts = PronunciationService(accent=self.settings.accent, on_error=self._log_warning_text)

        self.scheduler = QtScheduler(
            settings_provider=lambda: self.settings,
            idle_seconds_provider=self._idle_monitor.get_idle_seconds,
            emit_action=self._handle_scheduler_action,
        )
        if self.settings.enabled:
            self.scheduler.start()

        if catalog_result.recovered_with_default and self.tray is not None:
            self.tray.show_message("oh my word", "Recovered the default Kaoyan wordbook.")

        if first_launch or not self._tray_ready():
            self.show_settings_window()

    def show_settings_window(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsDialog(self.settings)
            self.settings_window.accepted.connect(self._save_settings_from_dialog)
            self.settings_window.finished.connect(self._on_settings_window_finished)
        else:
            self.settings_window.set_settings(self.settings)

        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def pronounce_current_word(self) -> None:
        if self.current_word is None or self.settings.mute_pronunciation or self.tts is None:
            return
        if self.tts.speak(self.current_word.word, accent=self.settings.accent):
            self._update_progress(
                self.current_word.word,
                lambda progress: replace(progress, last_pronounced_at=_now_iso()),
            )

    def toggle_details(self) -> None:
        if self.current_word is None or self.card_popup is None or not self.card_popup.isVisible():
            return
        self.card_popup.set_details_expanded(not self.card_popup.is_details_expanded())
        self._update_progress(
            self.current_word.word,
            lambda progress: replace(progress, last_expanded_at=_now_iso()),
        )

    def mark_current_word_mastered(self) -> None:
        if self.current_word is None:
            return
        word_key = self.current_word.word
        self._update_progress(word_key, lambda progress: replace(progress, mastered=True))
        self._close_active_popup()
        if self.tray is not None:
            self.tray.show_message("oh my word", f"Marked '{word_key}' as mastered.")

    def exit(self) -> None:
        if self.scheduler is not None:
            self.scheduler.dispose()
        if self.hotkeys is not None:
            self.hotkeys.stop()
        if self.tray is not None:
            self.tray.destroy()
        self._close_active_popup()
        self._app.quit()

    def _handle_scheduler_action(self, action: SchedulerAction[WordEntry]) -> None:
        if action.kind is SchedulerActionKind.SHOW_WORD and action.word is not None:
            if self._has_active_popup():
                if self.scheduler is not None:
                    self.scheduler.enqueue_word(action.word)
                return
            self._show_word(action.word)
            return

        if action.kind is SchedulerActionKind.REQUEST_FRESH_WORD:
            self._request_fresh_word(manual=(action.reason == "manual"))

    def _request_fresh_word(self, *, manual: bool) -> None:
        result = select_next_word(
            self.catalog,
            self.learning_state,
            recent_window_size=DEFAULT_RECENT_WORDS_WINDOW,
            rng=self._rng,
        )
        if result.word is None:
            if result.should_pause and self.scheduler is not None and not manual:
                self.scheduler.pause()
            if self.tray is not None and result.notice_key == "all_mastered":
                self.tray.show_message("oh my word", "All unmastered words are exhausted.")
            return

        if self._has_active_popup():
            if self.scheduler is not None:
                decision = self.scheduler.enqueue_word(result.word)
                if not decision.accepted:
                    self._log_info("Queued word already occupied; keeping first queued item.")
            return

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
                duration_ms=max(3000, popup_duration_ms),
            )

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
        self.card_popup.pronounce.connect(lambda _: self.pronounce_current_word())
        self.card_popup.mark_mastered.connect(lambda _: self.mark_current_word_mastered())
        self.card_popup.closed.connect(self._on_popup_closed)
        self.barrage_popup.pronounce.connect(lambda _: self.pronounce_current_word())
        self.barrage_popup.mark_mastered.connect(lambda _: self.mark_current_word_mastered())
        self.barrage_popup.closed.connect(self._on_popup_closed)

    def _hotkey_sequences(self) -> dict[str, str]:
        return {
            "pronounce": self.settings.pronounce_hotkey,
            "toggle_details": self.settings.toggle_detail_hotkey,
            "trigger_now": self.settings.trigger_now_hotkey,
            "mark_mastered": self.settings.mark_mastered_hotkey,
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
        self._request_fresh_word(manual=True)
        if self.scheduler is not None:
            self.scheduler.reset()

    def _on_popup_closed(self) -> None:
        self.current_word = None

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
        return self.tray is not None and not self.tray.tray_icon.icon().isNull()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
