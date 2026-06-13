from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.fsrs_service import FsrsReviewService, ProjectReviewRating
from app.models import WordEntry
from app.study_store import StudyStore


def test_initializes_schema_idempotently(tmp_path: Path) -> None:
    db_path = tmp_path / "oh_my_word.sqlite3"
    store = StudyStore(db_path)

    store.initialize()
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "schema_migrations",
        "cards",
        "recent_words",
        "review_log",
        "app_state",
    }.issubset(tables)
    with sqlite3.connect(db_path) as conn:
        migrations = [
            row[0]
            for row in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]

    assert migrations == [1]


def test_imports_legacy_learning_state_without_deleting_file(tmp_path: Path) -> None:
    db_path = tmp_path / "oh_my_word.sqlite3"
    legacy_path = tmp_path / "learning_state.json"
    legacy_path.write_text(
        json.dumps(
            {
                "recent_words": ["abandon"],
                "progress": {
                    "abandon": {
                        "show_count": 3,
                        "last_shown_at": "2026-06-08T08:00:00+00:00",
                        "due_at": "2026-06-09T08:00:00+00:00",
                        "review_count": 2,
                        "known_count": 1,
                        "unknown_count": 1,
                        "stability": 1.5,
                        "difficulty": 4.8,
                        "last_rating": "known",
                        "mastered": False,
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = StudyStore(db_path)
    store.initialize()

    store.import_legacy_learning_state(legacy_path)

    assert legacy_path.exists()
    card = store.get_card("abandon")
    assert card is not None
    assert card.word == "abandon"
    assert card.show_count == 3
    assert card.known_count == 1
    assert card.unknown_count == 1
    assert card.stability == 1.5
    assert card.difficulty == 4.8


def test_selects_due_card_before_new_word(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3")
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)
    store.upsert_card_for_test("brisk", due_at=(now - timedelta(minutes=1)).isoformat())

    result = store.select_next_word([_entry("abandon"), _entry("brisk")], now=now)

    assert result.word is not None
    assert result.word.word == "brisk"


def test_selects_due_card_by_learning_need_weight(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3")
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)
    store.upsert_card_for_test(
        "abandon",
        due_at=(now - timedelta(minutes=5)).isoformat(),
        difficulty=3.0,
        stability=8.0,
        lapses=0,
        unknown_count=0,
        show_count=8,
    )
    store.upsert_card_for_test(
        "zeal",
        due_at=(now - timedelta(days=2)).isoformat(),
        difficulty=9.0,
        stability=0.5,
        lapses=3,
        unknown_count=4,
        show_count=1,
    )

    result = store.select_next_word(
        [_entry("abandon"), _entry("zeal")],
        now=now,
        rng=_HighestWeightRandom(),
    )

    assert result.word is not None
    assert result.word.word == "zeal"


def test_snoozed_card_is_not_selected_until_snooze_expires(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3")
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)
    store.upsert_card_for_test("abandon", due_at=(now - timedelta(minutes=1)).isoformat())
    store.snooze_word("abandon", until=now + timedelta(minutes=30))

    result = store.select_next_word([_entry("abandon"), _entry("brisk")], now=now)

    assert result.word is not None
    assert result.word.word == "brisk"


def test_global_snooze_returns_pause_signal(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3")
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)
    store.snooze_app(until=now + timedelta(minutes=30))

    result = store.select_next_word([_entry("abandon")], now=now)

    assert result.word is None
    assert result.should_pause
    assert result.notice_key == "app_snoozed"


def test_known_review_updates_card_and_writes_review_log(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3", fsrs_service=FsrsReviewService())
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)

    store.review_word("abandon", ProjectReviewRating.KNOWN, reviewed_at=now)

    card = store.get_card("abandon")
    logs = store.review_logs_for_test("abandon")
    assert card is not None
    assert card.known_count == 1
    assert card.unknown_count == 0
    assert card.fsrs_payload_json
    assert len(logs) == 1
    assert logs[0]["rating"] == "known"


def test_snooze_does_not_write_review_log(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3", fsrs_service=FsrsReviewService())
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)

    store.snooze_word("abandon", until=now + timedelta(minutes=30))

    assert store.review_logs_for_test("abandon") == []


def test_records_show_pronounce_expand_and_mastered_state(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3")
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)

    store.record_word_shown("abandon", shown_at=now)
    store.record_word_pronounced("abandon", pronounced_at=now + timedelta(seconds=1))
    store.record_word_expanded("abandon", expanded_at=now + timedelta(seconds=2))
    store.mark_word_mastered("abandon")

    card = store.get_card("abandon")
    assert card is not None
    assert card.show_count == 1
    assert card.mastered

    with sqlite3.connect(tmp_path / "oh_my_word.sqlite3") as conn:
        row = conn.execute(
            """
            SELECT last_shown_at, last_pronounced_at, last_expanded_at
            FROM cards
            WHERE word = 'abandon'
            """
        ).fetchone()
        recent_count = conn.execute("SELECT COUNT(*) FROM recent_words").fetchone()[0]

    assert row == (
        now.isoformat(),
        (now + timedelta(seconds=1)).isoformat(),
        (now + timedelta(seconds=2)).isoformat(),
    )
    assert recent_count == 1


def _entry(word: str) -> WordEntry:
    return WordEntry(
        word=word,
        ipa="/test/",
        part_of_speech="n.",
        definitions=[word],
        example_sentence=word,
        example_translation=word,
    )


class _HighestWeightRandom:
    def choices(
        self,
        population: list[WordEntry],
        weights: list[float],
        *,
        k: int,
    ) -> list[WordEntry]:
        assert k == 1
        selected_index = max(range(len(weights)), key=weights.__getitem__)
        return [population[selected_index]]
