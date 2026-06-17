from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.models import AppSettings, PronunciationContentMode, TtsProvider
from app.settings_window import SettingsDialog
from app.version import APP_VERSION


class SettingsDialogTtsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_round_trips_voxcpm_provider_settings(self) -> None:
        dialog = SettingsDialog(
            AppSettings(
                tts_provider=TtsProvider.VOXCPM_LOCAL,
                pronunciation_content_mode=PronunciationContentMode.EXAMPLE,
                voxcpm_endpoint="http://localhost:8810",
                voxcpm_timeout_seconds=25,
                voxcpm_install_root="D:\\OhMyWord\\voxcpm",
                voxcpm_model_cache_root="E:\\Models\\VoxCPM2",
                voxcpm_use_model_mirror=False,
                voxcpm_auto_start=True,
                voxcpm_voice_prompt="A calm English teacher voice.",
                voxcpm_stream_prebuffer_seconds=0.65,
            )
        )
        self.addCleanup(dialog.close)

        settings = dialog.get_settings()

        self.assertIs(settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
        self.assertIs(settings.pronunciation_content_mode, PronunciationContentMode.EXAMPLE)
        self.assertEqual(settings.voxcpm_endpoint, "http://localhost:8810")
        self.assertEqual(settings.voxcpm_timeout_seconds, 25)
        self.assertEqual(settings.voxcpm_install_root, "D:\\OhMyWord\\voxcpm")
        self.assertEqual(settings.voxcpm_model_cache_root, "E:\\Models\\VoxCPM2")
        self.assertFalse(settings.voxcpm_use_model_mirror)
        self.assertTrue(settings.voxcpm_auto_start)
        self.assertEqual(settings.voxcpm_voice_prompt, "A calm English teacher voice.")
        self.assertEqual(settings.voxcpm_stream_prebuffer_seconds, 0.65)

    def test_settings_dialog_has_categorized_tabs(self) -> None:
        dialog = SettingsDialog(AppSettings())
        self.addCleanup(dialog.close)

        labels = [dialog._tabs.tabText(index) for index in range(dialog._tabs.count())]

        self.assertEqual(labels, ["学习", "显示", "发音", "快捷键", "词库", "关于"])

    def test_about_tab_shows_version_and_changelog(self) -> None:
        dialog = SettingsDialog(AppSettings())
        self.addCleanup(dialog.close)

        self.assertIn(f"v{APP_VERSION}", dialog._version_label.text())
        self.assertIn("更新日志", dialog._changelog_view.toPlainText())
        self.assertIn("v0.1.8", dialog._changelog_view.toPlainText())
        self.assertIn("Qt 官方异步网络和音频播放链路", dialog._changelog_view.toPlainText())
        self.assertIn("同步探测 /health", dialog._changelog_view.toPlainText())
        self.assertIn("v0.1.5", dialog._changelog_view.toPlainText())
        self.assertIn("v0.1.3", dialog._changelog_view.toPlainText())
        self.assertIn("v0.1.2", dialog._changelog_view.toPlainText())
        self.assertIn("v0.1.1", dialog._changelog_view.toPlainText())

    def test_voxcpm_action_buttons_emit_signals(self) -> None:
        dialog = SettingsDialog(AppSettings())
        self.addCleanup(dialog.close)
        emitted: list[str] = []
        dialog.voxcpm_install_requested.connect(lambda: emitted.append("install"))
        dialog.voxcpm_start_requested.connect(lambda: emitted.append("start"))
        dialog.voxcpm_stop_requested.connect(lambda: emitted.append("stop"))
        dialog.voxcpm_health_check_requested.connect(lambda: emitted.append("check"))
        dialog.voxcpm_open_log_requested.connect(lambda: emitted.append("log"))

        dialog._voxcpm_install_button.click()
        dialog._voxcpm_start_button.click()
        dialog._voxcpm_stop_button.click()
        dialog._voxcpm_check_button.click()
        dialog._voxcpm_open_log_button.click()

        self.assertEqual(emitted, ["install", "start", "stop", "check", "log"])
