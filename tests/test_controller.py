from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import ANY, Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStyle, QSystemTrayIcon

from app.controller import AppController, AppPaths
from app.fsrs_service import ProjectReviewRating
from app.models import AppSettings, WordEntry, WordSelectionResult
from app.tray import TrayController
from app.words import WordCatalog


class AppPathsRuntimeTests(unittest.TestCase):
    def test_frozen_runtime_reads_data_from_meipass_and_writes_storage_next_to_exe(self) -> None:
        with TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / "Oh My Word"
            internal_dir = install_dir / "_internal"
            executable_path = install_dir / "oh-my-word-py.exe"

            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", str(internal_dir), create=True),
                patch.object(sys, "executable", str(executable_path)),
            ):
                paths = AppPaths.from_runtime()

            self.assertEqual(paths.root_dir, install_dir)
            self.assertEqual(paths.data_dir, internal_dir / "data")
            self.assertEqual(paths.wordbooks_dir, internal_dir / "data" / "wordbooks")
            self.assertEqual(paths.storage_dir, install_dir / "storage")
            self.assertEqual(paths.study_db_path, install_dir / "storage" / "oh_my_word.sqlite3")


class ControllerTrayReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_tray_is_not_ready_when_system_tray_is_unavailable(self) -> None:
        controller = AppController(self.app)
        icon = self.app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        controller.tray = TrayController(icon=icon)
        self.addCleanup(controller.tray.destroy)

        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            self.assertFalse(controller._tray_ready())


class ControllerPopupActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_hotkey_sequences_include_visible_popup_actions(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(
            known_hotkey="Ctrl+Alt+8",
            unknown_hotkey="Ctrl+Alt+9",
            dismiss_hotkey="Ctrl+Alt+0",
        )

        self.assertEqual(
            controller._hotkey_sequences(),
            {
                "pronounce": "Ctrl+Alt+1",
                "toggle_details": "Ctrl+Alt+2",
                "trigger_now": "Ctrl+Alt+3",
                "mark_mastered": "Ctrl+Alt+4",
                "known": "Ctrl+Alt+8",
                "unknown": "Ctrl+Alt+9",
                "dismiss": "Ctrl+Alt+0",
            },
        )

    def test_visible_popup_review_is_noop_without_visible_popup(self) -> None:
        controller = AppController(self.app)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.card_popup = Mock(isVisible=Mock(return_value=False))
        controller.barrage_popup = Mock(isVisible=Mock(return_value=False))
        controller.review_current_word = Mock()

        controller.review_visible_popup(known=True)

        controller.review_current_word.assert_not_called()

    def test_visible_popup_review_dispatches_when_popup_is_visible(self) -> None:
        controller = AppController(self.app)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.card_popup = Mock(isVisible=Mock(return_value=True))
        controller.barrage_popup = Mock(isVisible=Mock(return_value=False))
        controller.review_current_word = Mock()

        controller.review_visible_popup(known=False)

        controller.review_current_word.assert_called_once_with(known=False)

    def test_visible_popup_dismiss_is_noop_without_visible_popup(self) -> None:
        controller = AppController(self.app)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.card_popup = Mock(isVisible=Mock(return_value=False))
        controller.barrage_popup = Mock(isVisible=Mock(return_value=False))
        controller._close_active_popup = Mock()

        controller.dismiss_visible_popup()

        controller._close_active_popup.assert_not_called()

    def test_visible_popup_dismiss_closes_when_popup_is_visible(self) -> None:
        controller = AppController(self.app)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.card_popup = Mock(isVisible=Mock(return_value=False))
        controller.barrage_popup = Mock(isVisible=Mock(return_value=True))
        controller._close_active_popup = Mock()

        controller.dismiss_visible_popup()

        controller._close_active_popup.assert_called_once_with()

    def test_visible_popup_snooze_is_noop_without_visible_popup(self) -> None:
        controller = AppController(self.app)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.card_popup = Mock(isVisible=Mock(return_value=False))
        controller.barrage_popup = Mock(isVisible=Mock(return_value=False))
        controller.study_store = Mock()
        controller._close_active_popup = Mock()

        controller.snooze_visible_popup()

        controller.study_store.snooze_word.assert_not_called()
        controller._close_active_popup.assert_not_called()

    def test_visible_popup_snooze_records_current_word_and_closes(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(snooze_minutes=45)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.card_popup = Mock(isVisible=Mock(return_value=True))
        controller.barrage_popup = Mock(isVisible=Mock(return_value=False))
        controller.study_store = Mock()
        controller._close_active_popup = Mock()

        controller.snooze_visible_popup()

        controller.study_store.snooze_word.assert_called_once_with("focus", until=ANY)
        controller._close_active_popup.assert_called_once_with()

    def test_global_snooze_records_app_pause_and_closes_active_popup(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(snooze_minutes=30)
        controller.study_store = Mock()
        controller.tray = Mock()
        controller._close_active_popup = Mock()

        controller.snooze_app_for_default_duration()

        controller.study_store.snooze_app.assert_called_once_with(until=ANY)
        controller._close_active_popup.assert_called_once_with()

    def test_request_fresh_word_uses_study_store_selection(self) -> None:
        controller = AppController(self.app)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.catalog = WordCatalog.from_entries([entry])
        controller.study_store = Mock()
        controller.study_store.select_next_word.return_value = WordSelectionResult(
            word=entry,
            should_pause=False,
        )
        controller._show_word = Mock()

        controller._request_fresh_word(manual=True)

        controller.study_store.select_next_word.assert_called_once()
        controller._show_word.assert_called_once_with(entry)

    def test_show_word_records_display_in_study_store(self) -> None:
        controller = AppController(self.app)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.settings = AppSettings()
        controller.card_popup = Mock()
        controller.barrage_popup = Mock()
        controller.study_store = Mock()

        controller._show_word(entry)

        controller.study_store.record_word_shown.assert_called_once_with("focus", shown_at=ANY)

    def test_review_current_word_writes_known_rating_to_study_store(self) -> None:
        controller = AppController(self.app)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.study_store = Mock()
        controller._close_active_popup = Mock()

        controller.review_current_word(known=True)

        controller.study_store.review_word.assert_called_once_with(
            "focus",
            ProjectReviewRating.KNOWN,
            reviewed_at=ANY,
        )
        controller._close_active_popup.assert_called_once_with()

    def test_review_current_word_writes_unknown_rating_to_study_store(self) -> None:
        controller = AppController(self.app)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.study_store = Mock()
        controller._close_active_popup = Mock()

        controller.review_current_word(known=False)

        controller.study_store.review_word.assert_called_once_with(
            "focus",
            ProjectReviewRating.UNKNOWN,
            reviewed_at=ANY,
        )
        controller._close_active_popup.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
