from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.models import LearningState, WordEntry, WordProgress
from app.words import (
    RECOMMENDED_KAOYAN_LICENSE,
    RECOMMENDED_KAOYAN_SOURCE_URL,
    WordCatalog,
    download_recommended_kaoyan_wordbook,
    ensure_default_wordbook,
    import_wordbook_file,
    load_word_catalog,
    select_next_word,
)


class LoadWordCatalogTests(unittest.TestCase):
    def test_load_word_catalog_sorts_files_and_later_duplicates_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbooks_dir = Path(temp_dir)
            self._write_wordbook(
                wordbooks_dir / "a-first.json",
                [
                    self._entry("abandon", "give up"),
                    self._entry("keen", "sharp"),
                ],
            )
            self._write_wordbook(
                wordbooks_dir / "b-second.json",
                [
                    self._entry("abandon", "leave behind"),
                    self._entry("derive", "obtain from"),
                ],
            )

            result = load_word_catalog(wordbooks_dir)

            self.assertEqual([], result.issues)
            self.assertEqual(["abandon", "derive", "keen"], [word.word for word in result.catalog.words])
            self.assertEqual(["leave behind"], result.catalog.by_word["abandon"].definitions)

    def test_load_word_catalog_skips_broken_json_and_reports_issue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbooks_dir = Path(temp_dir)
            self._write_wordbook(wordbooks_dir / "usable.json", [self._entry("abandon", "give up")])
            (wordbooks_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

            result = load_word_catalog(wordbooks_dir)

            self.assertEqual(["abandon"], [word.word for word in result.catalog.words])
            self.assertEqual(1, len(result.issues))
            self.assertIn("broken.json", Path(result.issues[0].source).name)

    def test_load_word_catalog_recovers_when_directory_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbooks_dir = Path(temp_dir) / "wordbooks"

            result = load_word_catalog(wordbooks_dir)

            self.assertTrue(wordbooks_dir.exists())
            self.assertGreaterEqual(len(result.catalog.words), 10)
            self.assertTrue(result.recovered_with_default)
            self.assertTrue((wordbooks_dir / "kaoyan_core.json").exists())

    def test_load_word_catalog_recovers_when_no_usable_words_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbooks_dir = Path(temp_dir)
            self._write_wordbook(wordbooks_dir / "empty.json", [])
            (wordbooks_dir / "broken.json").write_text("{oops", encoding="utf-8")

            result = load_word_catalog(wordbooks_dir)

            self.assertTrue(result.recovered_with_default)
            self.assertGreaterEqual(len(result.catalog.words), 10)
            self.assertGreaterEqual(len(result.issues), 1)

    def test_ensure_default_wordbook_is_idempotent_and_utf8_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            wordbooks_dir = Path(temp_dir)

            created = ensure_default_wordbook(wordbooks_dir)
            ensured = ensure_default_wordbook(wordbooks_dir)

            self.assertEqual(created, ensured)
            data = json.loads(created.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(data), 10)
            self.assertIn("exam", data[0]["example_sentence"].lower())

    def test_import_wordbook_file_accepts_flexible_json_and_converts_to_local_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "custom.json"
            target_dir = root / "wordbooks"
            source.write_text(
                json.dumps(
                    [
                        {
                            "term": "focus",
                            "phonetic": "/focus/",
                            "pos": "noun",
                            "translation": "重点；焦点",
                            "example": "Focus on review.",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = import_wordbook_file(source, target_dir)
            payload = json.loads(result.path.read_text(encoding="utf-8"))

            self.assertEqual(1, result.imported_count)
            self.assertEqual("focus", payload[0]["word"])
            self.assertEqual(["重点", "焦点"], payload[0]["definitions"])

    def test_import_wordbook_file_accepts_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "custom.csv"
            target_dir = root / "wordbooks"
            source.write_text(
                "word,ipa,part_of_speech,definitions,example_sentence,example_translation\n"
                "focus,/focus/,noun,重点|焦点,Focus on review.,专注复习。\n",
                encoding="utf-8",
            )

            result = import_wordbook_file(source, target_dir)
            payload = json.loads(result.path.read_text(encoding="utf-8"))

            self.assertEqual(1, result.imported_count)
            self.assertEqual("focus", payload[0]["word"])
            self.assertEqual(["重点", "焦点"], payload[0]["definitions"])

    def test_import_wordbook_file_accepts_nested_common_wordbook_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "nested.json"
            target_dir = root / "wordbooks"
            source.write_text(
                json.dumps(
                    [
                        {
                            "content": {
                                "word": {"wordHead": "derive"},
                                "trans": [{"tranCn": "获得；推导"}],
                            }
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = import_wordbook_file(source, target_dir)
            payload = json.loads(result.path.read_text(encoding="utf-8"))

            self.assertEqual(1, result.imported_count)
            self.assertEqual("derive", payload[0]["word"])
            self.assertEqual(["获得", "推导"], payload[0]["definitions"])

    def test_recommended_kaoyan_source_uses_netem_vocabulary(self) -> None:
        self.assertIn("exam-data/NETEMVocabulary", RECOMMENDED_KAOYAN_SOURCE_URL)
        self.assertEqual("CC BY-NC-SA 4.0", RECOMMENDED_KAOYAN_LICENSE)

    def test_download_recommended_kaoyan_wordbook_converts_payload_to_local_format(self) -> None:
        class _Response:
            def __enter__(self) -> "_Response":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    [
                        {
                            "content": {
                                "word": {"wordHead": "derive"},
                                "trans": [{"tranCn": "获得；推导"}],
                            }
                        }
                    ],
                    ensure_ascii=False,
                ).encode("utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.words.urlopen", return_value=_Response()):
                result = download_recommended_kaoyan_wordbook(Path(temp_dir))

            payload = json.loads(result.path.read_text(encoding="utf-8"))
            self.assertEqual("kaoyan_full.json", result.path.name)
            self.assertEqual(1, result.imported_count)
            self.assertEqual("derive", payload[0]["word"])
            self.assertEqual(["获得", "推导"], payload[0]["definitions"])

    @staticmethod
    def _write_wordbook(path: Path, entries: list[dict[str, object]]) -> None:
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _entry(word: str, definition: str) -> dict[str, object]:
        return {
            "word": word,
            "ipa": f"/{word}/",
            "part_of_speech": "verb",
            "definitions": [definition],
            "example_sentence": f"Example sentence for {word}.",
            "example_translation": f"{word} 的例句。",
        }


class SelectNextWordTests(unittest.TestCase):
    def test_select_next_word_excludes_mastered_then_recent(self) -> None:
        catalog = WordCatalog.from_entries(
            [
                self._word("abandon"),
                self._word("brisk"),
                self._word("candid"),
            ]
        )
        state = LearningState(
            recent_words=["brisk"],
            progress={"abandon": WordProgress(mastered=True)},
        )

        result = select_next_word(catalog, state, recent_window_size=2)

        self.assertEqual("candid", result.word.word if result.word else None)
        self.assertFalse(result.should_pause)
        self.assertIsNone(result.notice_key)

    def test_select_next_word_falls_back_when_recent_filter_exhausts_unmastered_pool(self) -> None:
        catalog = WordCatalog.from_entries([self._word("abandon"), self._word("brisk")])
        state = LearningState(recent_words=["abandon", "brisk"])

        result = select_next_word(catalog, state, recent_window_size=2)

        self.assertIn(result.word.word if result.word else None, {"abandon", "brisk"})
        self.assertTrue(result.used_recent_fallback)

    def test_select_next_word_returns_pause_signal_when_everything_is_mastered(self) -> None:
        catalog = WordCatalog.from_entries([self._word("abandon"), self._word("brisk")])
        state = LearningState(
            progress={
                "abandon": WordProgress(mastered=True),
                "brisk": WordProgress(mastered=True),
            }
        )

        result = select_next_word(catalog, state)

        self.assertIsNone(result.word)
        self.assertTrue(result.should_pause)
        self.assertEqual("all_mastered", result.notice_key)

    def test_select_next_word_uses_only_short_recent_window(self) -> None:
        catalog = WordCatalog.from_entries(
            [
                self._word("abandon"),
                self._word("brisk"),
                self._word("candid"),
            ]
        )
        state = LearningState(recent_words=["abandon", "brisk", "candid"])

        result = select_next_word(catalog, state, recent_window_size=1)

        self.assertIn(result.word.word if result.word else None, {"abandon", "brisk"})

    def test_select_next_word_prioritizes_due_reviews_before_new_words(self) -> None:
        now = datetime(2026, 5, 30, 10, 0, tzinfo=UTC)
        catalog = WordCatalog.from_entries([self._word("abandon"), self._word("brisk")])
        state = LearningState(
            progress={
                "brisk": WordProgress(
                    due_at=(now - timedelta(minutes=1)).isoformat(),
                    review_count=1,
                )
            }
        )

        result = select_next_word(catalog, state, now=now)

        self.assertEqual("brisk", result.word.word if result.word else None)

    @staticmethod
    def _word(word: str) -> WordEntry:
        return WordEntry(
            word=word,
            ipa=f"/{word}/",
            part_of_speech="noun",
            definitions=[f"{word} definition"],
            example_sentence=f"Use {word} in a sentence.",
            example_translation=f"{word} 的例句。",
        )


if __name__ == "__main__":
    unittest.main()
