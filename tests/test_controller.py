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
from app.models import (
    AppSettings,
    DEFAULT_VOXCPM_INSTALL_ROOT,
    DEFAULT_VOXCPM_MODEL_CACHE_ROOT,
    PronunciationContentMode,
    TtsInitializationState,
    TtsProvider,
    WordEntry,
    WordSelectionResult,
)
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

    def test_pronounce_text_reads_supplied_popup_text_and_records_current_word(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.speak.return_value = True
        controller.study_store = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.tts.speak.assert_called_once_with("focus. Focus on review.", accent=controller.settings.accent)
        controller.study_store.record_word_pronounced.assert_called_once_with("focus", pronounced_at=ANY)

    def test_voxcpm_pronounce_text_defers_record_until_async_playback_started(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(tts_provider=TtsProvider.VOXCPM_LOCAL)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.study_store = Mock()
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.is_running.return_value = True
        captured: dict[str, object] = {}

        def fake_speak(text: str, *, accent: object | None = None, request_tag: object | None = None) -> bool:
            captured["text"] = text
            captured["accent"] = accent
            captured["request_tag"] = request_tag
            return True

        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.provider = TtsProvider.VOXCPM_LOCAL
        controller.tts.speak.side_effect = fake_speak

        controller.pronounce_text("focus. Focus on review.")

        self.assertEqual(captured["text"], '"focus". Focus on review.')
        controller.study_store.record_word_pronounced.assert_not_called()

        controller._on_tts_playback_started(captured["request_tag"])

        controller.study_store.record_word_pronounced.assert_called_once_with("focus", pronounced_at=ANY)

    def test_pronounce_current_word_uses_configured_pronunciation_content_mode(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(pronunciation_content_mode=PronunciationContentMode.EXAMPLE)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.pronounce_text = Mock()

        controller.pronounce_current_word()

        controller.pronounce_text.assert_called_once_with("Focus on review.")

    def test_show_word_schedules_auto_pronounce_when_enabled(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(
            auto_pronounce_on_popup=True,
            auto_pronounce_delay_seconds=1.25,
        )
        controller.card_popup = Mock()
        controller.barrage_popup = Mock()
        controller.study_store = Mock()
        controller._auto_pronounce_timer = Mock()
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")

        controller._show_word(entry)

        controller._auto_pronounce_timer.start.assert_called_once_with(1250)

    def test_pronounce_text_cancels_pending_auto_pronounce(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(auto_pronounce_on_popup=True)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.speak.return_value = True
        controller.study_store = Mock()
        controller._auto_pronounce_timer = Mock()
        controller._pending_auto_pronounce_word = "focus"

        controller.pronounce_text("focus")

        controller._auto_pronounce_timer.stop.assert_called_once_with()

    def test_auto_pronounce_timeout_ignores_closed_popup(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(auto_pronounce_on_popup=True)
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        controller.card_popup = Mock(isVisible=Mock(return_value=False))
        controller.barrage_popup = Mock(isVisible=Mock(return_value=False))
        controller.pronounce_current_word = Mock()
        controller._pending_auto_pronounce_word = "focus"

        controller._trigger_auto_pronounce()

        controller.pronounce_current_word.assert_not_called()

    def test_pronounce_failure_does_not_record_pronounced_at(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.speak.return_value = False
        controller.study_store = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.tts.speak.assert_called_once_with("focus. Focus on review.", accent=controller.settings.accent)
        controller.study_store.record_word_pronounced.assert_not_called()

    def test_tts_playback_failed_shows_notice(self) -> None:
        controller = AppController(self.app)
        controller.tray = Mock()

        controller._on_tts_playback_failed(("req-1", "focus"), "Streaming VoxCPM audio failed.")

        controller.tray.show_message.assert_called_once_with("oh my word", "语音朗读失败：Streaming VoxCPM audio failed.")

    def test_pronounce_text_shows_initialization_notice_when_tts_is_not_ready(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.NOT_INITIALIZED
        controller.tts.provider = TtsProvider.SYSTEM_QT
        controller.tts.speak = Mock()
        controller.tray = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.tts.speak.assert_not_called()
        controller.tray.show_message.assert_called_once_with("oh my word", "语音正在初始化，请稍后")

    def test_pronounce_text_throttles_initialization_notice(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.INITIALIZING
        controller.tts.provider = TtsProvider.SYSTEM_QT
        controller.tts.speak = Mock()
        controller.tray = Mock()

        with patch("app.controller.monotonic", side_effect=[100.0, 101.0]):
            controller.pronounce_text("focus. Focus on review.")
            controller.pronounce_text("focus. Focus on review.")

        controller.tts.speak.assert_not_called()
        controller.tray.show_message.assert_called_once_with("oh my word", "语音正在初始化，请稍后")

    def test_pronounce_text_shows_unavailable_reason_when_tts_is_unavailable(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.UNAVAILABLE
        controller.tts.provider = TtsProvider.SYSTEM_QT
        controller.tts.last_error = "PySide6 QtTextToSpeech is not installed."
        controller.tts.speak = Mock()
        controller.tray = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.tts.speak.assert_not_called()
        controller.tray.show_message.assert_called_once_with(
            "oh my word",
            "语音初始化失败：PySide6 QtTextToSpeech is not installed.",
        )

    def test_apply_settings_rebuilds_tts_when_provider_changes(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.settings_store = Mock()
        controller.hotkeys = Mock()
        controller.hotkeys.registration_errors = {}
        controller.tray = Mock()
        controller.scheduler = Mock()
        controller.tts = Mock()
        old_tts = controller.tts

        new_settings = AppSettings(tts_provider=TtsProvider.VOXCPM_LOCAL)

        with patch("app.controller.PronunciationService") as service_class:
            service_class.return_value = Mock()
            controller._apply_settings(new_settings)

        old_tts.stop.assert_called_once_with()
        service_class.assert_called_once()
        self.assertIs(controller.settings.tts_provider, TtsProvider.VOXCPM_LOCAL)

    def test_apply_settings_rebuilds_tts_when_voxcpm_stream_prebuffer_changes(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(
            tts_provider=TtsProvider.VOXCPM_LOCAL,
            voxcpm_stream_prebuffer_seconds=0.35,
        )
        controller.settings_store = Mock()
        controller.hotkeys = Mock()
        controller.hotkeys.registration_errors = {}
        controller.tray = Mock()
        controller.scheduler = Mock()
        controller.tts = Mock()
        old_tts = controller.tts

        new_settings = AppSettings(
            tts_provider=TtsProvider.VOXCPM_LOCAL,
            voxcpm_stream_prebuffer_seconds=0.75,
        )

        with patch("app.controller.PronunciationService") as service_class:
            service_class.return_value = Mock()
            controller._apply_settings(new_settings)

        old_tts.stop.assert_called_once_with()
        self.assertEqual(service_class.call_args.kwargs["stream_prebuffer_seconds"], 0.75)

    def test_pronounce_text_autostarts_installed_voxcpm_when_enabled(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(
            tts_provider=TtsProvider.VOXCPM_LOCAL,
            voxcpm_auto_start=True,
        )
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.provider = TtsProvider.VOXCPM_LOCAL
        controller.tts.speak = Mock()
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.is_installed.return_value = True
        controller.voxcpm_service.is_running.return_value = False
        controller.voxcpm_service.start_service.return_value = True
        controller.tray = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.voxcpm_service.start_service.assert_called_once_with()
        controller.voxcpm_service.health_check.assert_not_called()
        controller.tts.speak.assert_not_called()
        controller.tray.show_message.assert_called_once_with("oh my word", "VoxCPM 本地服务正在启动，请稍后再试。")

    def test_pronounce_text_does_not_autoinstall_missing_voxcpm(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(
            tts_provider=TtsProvider.VOXCPM_LOCAL,
            voxcpm_auto_start=True,
        )
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.provider = TtsProvider.VOXCPM_LOCAL
        controller.tts.speak = Mock()
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.is_installed.return_value = False
        controller.voxcpm_service.is_running.return_value = False
        controller.tray = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.voxcpm_service.health_check.assert_not_called()
        controller.voxcpm_service.start_service.assert_not_called()
        controller.tts.speak.assert_not_called()
        controller.tray.show_message.assert_called_once_with(
            "oh my word",
            "VoxCPM 尚未就绪，请先在设置中导入运行时包，或使用后台安装 / 更新作为兼容方案。",
        )

    def test_pronounce_text_uses_voxcpm_when_service_is_running(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(
            tts_provider=TtsProvider.VOXCPM_LOCAL,
            voxcpm_auto_start=True,
        )
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.provider = TtsProvider.VOXCPM_LOCAL
        controller.tts.speak.return_value = True
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.is_running.return_value = True
        controller.study_store = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.voxcpm_service.health_check.assert_not_called()
        controller.voxcpm_service.start_service.assert_not_called()
        controller.tts.speak.assert_called_once_with(
            '"focus". Focus on review.',
            accent=controller.settings.accent,
            request_tag=ANY,
        )

    def test_pronounce_text_formats_voxcpm_prompt_and_quotes_word(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings(
            tts_provider=TtsProvider.VOXCPM_LOCAL,
            pronunciation_content_mode=PronunciationContentMode.WORD_AND_EXAMPLE,
            voxcpm_voice_prompt="A calm English teacher voice.",
        )
        controller.current_word = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        controller.tts = Mock()
        controller.tts.initialization_state = TtsInitializationState.READY
        controller.tts.provider = TtsProvider.VOXCPM_LOCAL
        controller.tts.speak.return_value = True
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.is_running.return_value = True
        controller.study_store = Mock()

        controller.pronounce_text("focus. Focus on review.")

        controller.tts.speak.assert_called_once_with(
            '(A calm English teacher voice.)"focus". Focus on review.',
            accent=controller.settings.accent,
            request_tag=ANY,
        )

    def test_apply_settings_reconfigures_voxcpm_manager(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.settings_store = Mock()
        controller.hotkeys = Mock()
        controller.hotkeys.registration_errors = {}
        controller.tray = Mock()
        controller.scheduler = Mock()
        controller.tts = Mock()
        controller.voxcpm_service = Mock()

        new_settings = AppSettings(
            voxcpm_install_root="D:\\OhMyWord\\voxcpm",
            voxcpm_model_cache_root="E:\\Models\\VoxCPM2",
            voxcpm_use_model_mirror=False,
            voxcpm_endpoint="http://localhost:8810",
        )

        controller._apply_settings(new_settings)

        controller.voxcpm_service.configure.assert_called_once_with(
            install_root=Path("D:\\OhMyWord\\voxcpm"),
            model_cache_root=Path("E:\\Models\\VoxCPM2"),
            endpoint="http://localhost:8810",
            use_model_mirror=False,
        )

    def test_check_voxcpm_service_applies_open_settings_dialog_values_before_refreshing(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.settings_store = Mock()
        controller.settings_window = Mock()
        current_settings = AppSettings(
            voxcpm_install_root="D:\\OhMyWord\\voxcpm",
            voxcpm_model_cache_root="E:\\Models\\VoxCPM2",
            voxcpm_use_model_mirror=False,
            voxcpm_endpoint="http://localhost:8810",
        )
        controller.settings_window.get_settings.return_value = current_settings
        controller.settings_store.save.return_value = current_settings
        controller.tray = Mock()
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.health_check.return_value = False
        controller.voxcpm_service.status.return_value.message = "VoxCPM 服务未响应。"

        controller.check_voxcpm_service()

        controller.settings_store.save.assert_called_once_with(current_settings)
        controller.voxcpm_service.configure.assert_called_once_with(
            install_root=Path("D:\\OhMyWord\\voxcpm"),
            model_cache_root=Path("E:\\Models\\VoxCPM2"),
            endpoint="http://localhost:8810",
            use_model_mirror=False,
        )
        controller.voxcpm_service.health_check.assert_called_once_with()
        controller.tray.show_message.assert_called_once_with("oh my word", "VoxCPM 服务未响应。")

    def test_import_voxcpm_runtime_package_uses_file_dialog_and_manager(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.settings_store = Mock()
        controller.settings_window = Mock()
        current_settings = AppSettings(
            voxcpm_install_root="D:\\OhMyWord\\tts\\voxcpm",
            voxcpm_model_cache_root="D:\\OhMyWord\\tts\\voxcpm\\models",
        )
        controller.settings_window.get_settings.return_value = current_settings
        controller.settings_store.save.return_value = current_settings
        controller.tray = Mock()
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.import_runtime_package.return_value = True

        with patch("app.controller.QFileDialog.getOpenFileName", return_value=("D:\\Downloads\\runtime.zip", "zip")):
            controller.import_voxcpm_runtime_package()

        controller.settings_store.save.assert_called_once_with(current_settings)
        controller.voxcpm_service.import_runtime_package.assert_called_once_with(Path("D:\\Downloads\\runtime.zip"))
        controller.tray.show_message.assert_called_once_with("oh my word", "VoxCPM 运行时包导入成功。")

    def test_import_voxcpm_model_package_uses_file_dialog_and_manager(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.settings_store = Mock()
        controller.settings_window = Mock()
        current_settings = AppSettings()
        controller.settings_window.get_settings.return_value = current_settings
        controller.settings_store.save.return_value = current_settings
        controller.tray = Mock()
        controller.voxcpm_service = Mock()
        controller.voxcpm_service.import_model_package.return_value = True

        with patch("app.controller.QFileDialog.getOpenFileName", return_value=("D:\\Downloads\\model.zip", "zip")):
            controller.import_voxcpm_model_package()

        controller.voxcpm_service.import_model_package.assert_called_once_with(Path("D:\\Downloads\\model.zip"))
        controller.tray.show_message.assert_called_once_with("oh my word", "VoxCPM 模型包导入成功。")

    def test_download_voxcpm_runtime_bundle_uses_manager(self) -> None:
        controller = AppController(self.app)
        controller.settings = AppSettings()
        controller.settings_store = Mock()
        controller.settings_window = Mock()
        current_settings = AppSettings()
        controller.settings_window.get_settings.return_value = current_settings
        controller.settings_store.save.return_value = current_settings
        controller.tray = Mock()
        controller.voxcpm_service = Mock()

        controller.download_and_import_voxcpm_runtime_bundle()

        controller.voxcpm_service.download_and_import_runtime_bundle.assert_called_once()

    def test_create_tts_service_passes_voxcpm_stream_prebuffer_seconds(self) -> None:
        controller = AppController(self.app)
        with TemporaryDirectory() as temp_dir:
            controller._paths = AppPaths(
                root_dir=Path(temp_dir),
                data_dir=Path(temp_dir) / "data",
                wordbooks_dir=Path(temp_dir) / "data" / "wordbooks",
                storage_dir=Path(temp_dir) / "storage",
                settings_path=Path(temp_dir) / "storage" / "settings.json",
                learning_state_path=Path(temp_dir) / "storage" / "learning_state.json",
                log_path=Path(temp_dir) / "storage" / "app.log",
                study_db_path=Path(temp_dir) / "storage" / "oh_my_word.sqlite3",
            )
            controller.settings = AppSettings(
                tts_provider=TtsProvider.VOXCPM_LOCAL,
                voxcpm_stream_prebuffer_seconds=0.9,
            )

            with patch("app.controller.PronunciationService") as service_class:
                service_class.return_value = Mock()
                controller._create_tts_service()

        self.assertEqual(service_class.call_args.kwargs["stream_prebuffer_seconds"], 0.9)

    def test_runtime_voxcpm_defaults_use_app_tts_directory_when_settings_are_default(self) -> None:
        controller = AppController(self.app)
        with TemporaryDirectory() as temp_dir:
            controller._paths = AppPaths(
                root_dir=Path(temp_dir) / "Oh My Word",
                data_dir=Path(temp_dir) / "Oh My Word" / "_internal" / "data",
                wordbooks_dir=Path(temp_dir) / "Oh My Word" / "_internal" / "data" / "wordbooks",
                storage_dir=Path(temp_dir) / "Oh My Word" / "storage",
                settings_path=Path(temp_dir) / "Oh My Word" / "storage" / "settings.json",
                learning_state_path=Path(temp_dir) / "Oh My Word" / "storage" / "learning_state.json",
                log_path=Path(temp_dir) / "Oh My Word" / "storage" / "app.log",
                study_db_path=Path(temp_dir) / "Oh My Word" / "storage" / "oh_my_word.sqlite3",
            )

            settings = controller._settings_with_runtime_voxcpm_defaults(AppSettings())

        expected_root = Path(temp_dir) / "Oh My Word" / "tts" / "voxcpm"
        self.assertEqual(settings.voxcpm_install_root, str(expected_root))
        self.assertEqual(settings.voxcpm_model_cache_root, str(expected_root / "models"))

    def test_runtime_voxcpm_defaults_do_not_override_custom_paths(self) -> None:
        controller = AppController(self.app)
        controller._paths = AppPaths.from_root(Path("C:\\Apps\\Oh My Word"))

        settings = controller._settings_with_runtime_voxcpm_defaults(
            AppSettings(
                voxcpm_install_root="D:\\TTS\\voxcpm",
                voxcpm_model_cache_root="E:\\Models\\VoxCPM2",
            )
        )

        self.assertEqual(settings.voxcpm_install_root, "D:\\TTS\\voxcpm")
        self.assertEqual(settings.voxcpm_model_cache_root, "E:\\Models\\VoxCPM2")

    def test_runtime_voxcpm_defaults_migrate_old_default_paths(self) -> None:
        controller = AppController(self.app)
        controller._paths = AppPaths.from_root(Path("C:\\Apps\\Oh My Word"))

        settings = controller._settings_with_runtime_voxcpm_defaults(
            AppSettings(
                voxcpm_install_root=DEFAULT_VOXCPM_INSTALL_ROOT,
                voxcpm_model_cache_root=DEFAULT_VOXCPM_MODEL_CACHE_ROOT,
            )
        )

        self.assertEqual(settings.voxcpm_install_root, "C:\\Apps\\Oh My Word\\tts\\voxcpm")
        self.assertEqual(settings.voxcpm_model_cache_root, "C:\\Apps\\Oh My Word\\tts\\voxcpm\\models")

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

        controller.card_popup.show_popup.assert_called_once_with(
            entry,
            position=controller.settings.card_position,
            auto_hide_ms=controller.settings.popup_duration_seconds * 1000,
            pronunciation_content_mode=PronunciationContentMode.WORD_AND_EXAMPLE,
        )
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
