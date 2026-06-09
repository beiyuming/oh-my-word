from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtWidgets import QApplication

from app.models import OverlayPosition, WordEntry
from app.overlays.barrage_popup import BarragePopup, compute_barrage_rect
from app.overlays.card_popup import CardPopup, compute_popup_rect


class CardPopupGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_random_card_position_stays_within_screen_bounds(self) -> None:
        screen = QRect(100, 50, 1280, 720)
        size = QSize(420, 180)

        with patch("app.overlays.card_popup._screen_rect", return_value=screen), patch(
            "app.overlays.card_popup.randint",
            side_effect=[screen.x() + 150, screen.y() + 120],
            create=True,
        ):
            rect = compute_popup_rect(size, OverlayPosition.RANDOM)

        self.assertEqual(rect.topLeft(), QPoint(screen.x() + 150, screen.y() + 120))
        self.assertGreaterEqual(rect.left(), screen.left() + 24)
        self.assertGreaterEqual(rect.top(), screen.top() + 24)
        self.assertLessEqual(rect.right(), screen.right() - 24)
        self.assertLessEqual(rect.bottom(), screen.bottom() - 24)

    def test_card_popup_emits_snoozed_word(self) -> None:
        popup = CardPopup()
        self.addCleanup(popup.deleteLater)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        captured: list[str] = []
        popup.snoozed.connect(captured.append)

        popup.set_entry(entry)
        popup.snooze_button.click()

        self.assertEqual(captured, ["focus"])

    def test_card_popup_details_include_example_sentence_and_translation(self) -> None:
        popup = CardPopup()
        self.addCleanup(popup.deleteLater)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")

        popup.set_entry(entry)

        self.assertIn("例句", popup.details_label.text())
        self.assertIn("Focus on review.", popup.details_label.text())
        self.assertIn("专注复习。", popup.details_label.text())

    def test_card_popup_pronounce_emits_word_and_example_sentence(self) -> None:
        popup = CardPopup()
        self.addCleanup(popup.deleteLater)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        captured: list[str] = []
        popup.pronounce.connect(captured.append)

        popup.set_entry(entry)
        popup.pronounce_button.click()

        self.assertEqual(captured, ["focus. Focus on review."])


class BarragePopupGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_random_barrage_position_stays_within_screen_bounds(self) -> None:
        screen = QRect(0, 0, 1280, 720)
        size = QSize(520, 120)

        with patch("app.overlays.barrage_popup._screen_rect", return_value=screen), patch(
            "app.overlays.barrage_popup.randint",
            return_value=222,
        ):
            rect = compute_barrage_rect(size, OverlayPosition.RANDOM)

        self.assertEqual(rect.top(), 222)
        self.assertLessEqual(rect.bottom(), screen.bottom() - 20)

    def test_barrage_animation_ends_after_popup_fully_leaves_screen(self) -> None:
        popup = BarragePopup()
        self.addCleanup(popup.deleteLater)
        popup.resize(520, 120)
        screen = QRect(0, 0, 1280, 720)

        with patch("app.overlays.barrage_popup._screen_rect", return_value=screen):
            popup.start_animation(anchor=None)

        self.assertEqual(popup._animation.endValue(), QPoint(screen.x() - popup.width() - 12, popup.y()))

    def test_barrage_popup_emits_snoozed_word(self) -> None:
        popup = BarragePopup()
        self.addCleanup(popup.deleteLater)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus now.", "现在专注。")
        captured: list[str] = []
        popup.snoozed.connect(captured.append)

        popup.set_entry(entry)
        popup.snooze_button.click()

        self.assertEqual(captured, ["focus"])

    def test_barrage_popup_details_include_example_sentence_and_translation(self) -> None:
        popup = BarragePopup()
        self.addCleanup(popup.deleteLater)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")

        popup.set_entry(entry)

        self.assertIn("例句", popup.details_label.text())
        self.assertIn("Focus on review.", popup.details_label.text())
        self.assertIn("专注复习。", popup.details_label.text())

    def test_barrage_popup_pronounce_emits_word_and_example_sentence(self) -> None:
        popup = BarragePopup()
        self.addCleanup(popup.deleteLater)
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        captured: list[str] = []
        popup.pronounce.connect(captured.append)

        popup.set_entry(entry)
        popup.pronounce_button.click()

        self.assertEqual(captured, ["focus. Focus on review."])
