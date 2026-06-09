from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.models import AppSettings, TtsProvider
from app.settings_window import SettingsDialog


class SettingsDialogTtsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_round_trips_voxcpm_provider_settings(self) -> None:
        dialog = SettingsDialog(
            AppSettings(
                tts_provider=TtsProvider.VOXCPM_LOCAL,
                voxcpm_endpoint="http://localhost:8810",
                voxcpm_timeout_seconds=25,
            )
        )
        self.addCleanup(dialog.close)

        settings = dialog.get_settings()

        self.assertIs(settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
        self.assertEqual(settings.voxcpm_endpoint, "http://localhost:8810")
        self.assertEqual(settings.voxcpm_timeout_seconds, 25)
