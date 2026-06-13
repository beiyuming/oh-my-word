from __future__ import annotations

import unittest

from app.models import PronunciationContentMode, WordEntry
from app.pronunciation import pronunciation_text, voxcpm_pronunciation_text


class PronunciationTextTests(unittest.TestCase):
    def test_word_and_example_uses_clear_pause_between_word_and_sentence(self) -> None:
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")

        self.assertEqual(
            pronunciation_text(entry, PronunciationContentMode.WORD_AND_EXAMPLE),
            "focus.\n\nFocus on review.",
        )

    def test_word_mode_reads_only_word(self) -> None:
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")

        self.assertEqual(pronunciation_text(entry, PronunciationContentMode.WORD), "focus")

    def test_example_mode_reads_only_example_and_falls_back_to_word(self) -> None:
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")
        without_example = WordEntry("focus", "/f/", "verb", ["聚焦"], "", "")

        self.assertEqual(pronunciation_text(entry, PronunciationContentMode.EXAMPLE), "Focus on review.")
        self.assertEqual(pronunciation_text(without_example, PronunciationContentMode.EXAMPLE), "focus")

    def test_duplicate_example_does_not_repeat_word(self) -> None:
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], " Focus ", "专注。")

        self.assertEqual(
            pronunciation_text(entry, PronunciationContentMode.WORD_AND_EXAMPLE),
            "focus",
        )

    def test_voxcpm_word_and_example_quotes_word_and_applies_voice_prompt(self) -> None:
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")

        self.assertEqual(
            voxcpm_pronunciation_text(
                entry,
                PronunciationContentMode.WORD_AND_EXAMPLE,
                voice_prompt="A calm English teacher voice.",
            ),
            '(A calm English teacher voice.)"focus". Focus on review.',
        )

    def test_voxcpm_example_mode_keeps_sentence_unquoted_but_uses_voice_prompt(self) -> None:
        entry = WordEntry("focus", "/f/", "verb", ["聚焦"], "Focus on review.", "专注复习。")

        self.assertEqual(
            voxcpm_pronunciation_text(
                entry,
                PronunciationContentMode.EXAMPLE,
                voice_prompt="A calm English teacher voice.",
            ),
            "(A calm English teacher voice.)Focus on review.",
        )


if __name__ == "__main__":
    unittest.main()
