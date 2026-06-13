from __future__ import annotations

import json
import logging
import random
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, Sequence

from .fsrs_service import FsrsReviewService, ProjectReviewRating
from .models import WordEntry, WordSelectionResult
from .settings import normalize_learning_state


SCHEMA_VERSION = 1
_MODULE_LOGGER = logging.getLogger("oh_my_word.study_store")


class WeightedRandomSource(Protocol):
    def choices(
        self,
        population: Sequence[WordEntry],
        weights: Sequence[float],
        *,
        k: int,
    ) -> list[WordEntry]:
        ...


@dataclass(slots=True, frozen=True)
class StudyCard:
    id: int
    word: str
    due_at: str | None
    state: str
    stability: float | None
    difficulty: float | None
    reps: int
    lapses: int
    mastered: bool
    suspended: bool
    snoozed_until: str | None
    show_count: int
    known_count: int
    unknown_count: int
    fsrs_payload_json: str | None


class StudyStore:
    def __init__(
        self,
        db_path: Path,
        logger: logging.Logger | None = None,
        fsrs_service: FsrsReviewService | None = None,
    ) -> None:
        self._db_path = db_path
        self._logger = logger or _MODULE_LOGGER
        self._fsrs_service = fsrs_service or FsrsReviewService()

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version INTEGER PRIMARY KEY,
                  applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cards (
                  id INTEGER PRIMARY KEY,
                  word TEXT NOT NULL UNIQUE,
                  due_at TEXT,
                  state TEXT NOT NULL DEFAULT 'new',
                  stability REAL,
                  difficulty REAL,
                  reps INTEGER NOT NULL DEFAULT 0,
                  lapses INTEGER NOT NULL DEFAULT 0,
                  mastered INTEGER NOT NULL DEFAULT 0,
                  suspended INTEGER NOT NULL DEFAULT 0,
                  snoozed_until TEXT,
                  last_shown_at TEXT,
                  last_pronounced_at TEXT,
                  last_expanded_at TEXT,
                  last_reviewed_at TEXT,
                  last_rating TEXT,
                  show_count INTEGER NOT NULL DEFAULT 0,
                  known_count INTEGER NOT NULL DEFAULT 0,
                  unknown_count INTEGER NOT NULL DEFAULT 0,
                  fsrs_payload_json TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recent_words (
                  id INTEGER PRIMARY KEY,
                  word TEXT NOT NULL,
                  shown_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_log (
                  id INTEGER PRIMARY KEY,
                  card_id INTEGER NOT NULL,
                  word TEXT NOT NULL,
                  reviewed_at TEXT NOT NULL,
                  rating TEXT NOT NULL,
                  state_before TEXT,
                  state_after TEXT,
                  scheduled_days INTEGER,
                  elapsed_days INTEGER,
                  duration_ms INTEGER,
                  fsrs_review_log_json TEXT,
                  FOREIGN KEY(card_id) REFERENCES cards(id)
                );

                CREATE TABLE IF NOT EXISTS app_state (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due_at);
                CREATE INDEX IF NOT EXISTS idx_cards_snoozed ON cards(snoozed_until);
                CREATE INDEX IF NOT EXISTS idx_cards_flags ON cards(mastered, suspended);
                CREATE INDEX IF NOT EXISTS idx_recent_words_shown_at ON recent_words(shown_at);
                CREATE INDEX IF NOT EXISTS idx_review_log_word_time ON review_log(word, reviewed_at);
                """
            )
            conn.execute(
                """
                INSERT INTO schema_migrations (version, applied_at)
                VALUES (?, ?)
                ON CONFLICT(version) DO NOTHING
                """,
                (SCHEMA_VERSION, _now_iso()),
            )

    def import_legacy_learning_state(self, legacy_path: Path) -> None:
        if not legacy_path.exists():
            return

        imported_marker = self._get_app_state("legacy_learning_state_imported_at")
        if imported_marker is not None:
            return

        try:
            payload = json.loads(legacy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._logger.warning("Failed to import legacy learning state %s: %s", legacy_path, exc)
            return

        state = normalize_learning_state(payload)
        imported_at = _now_iso()
        with self._connect() as conn:
            for word, progress in state.progress.items():
                review_count = max(progress.review_count, progress.known_count + progress.unknown_count)
                card_state = "review" if review_count > 0 or progress.due_at else "new"
                conn.execute(
                    """
                    INSERT INTO cards (
                      word,
                      due_at,
                      state,
                      stability,
                      difficulty,
                      reps,
                      mastered,
                      last_shown_at,
                      last_pronounced_at,
                      last_expanded_at,
                      last_reviewed_at,
                      last_rating,
                      show_count,
                      known_count,
                      unknown_count,
                      created_at,
                      updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(word) DO UPDATE SET
                      due_at = excluded.due_at,
                      state = excluded.state,
                      stability = excluded.stability,
                      difficulty = excluded.difficulty,
                      reps = excluded.reps,
                      mastered = excluded.mastered,
                      last_shown_at = excluded.last_shown_at,
                      last_pronounced_at = excluded.last_pronounced_at,
                      last_expanded_at = excluded.last_expanded_at,
                      last_reviewed_at = excluded.last_reviewed_at,
                      last_rating = excluded.last_rating,
                      show_count = excluded.show_count,
                      known_count = excluded.known_count,
                      unknown_count = excluded.unknown_count,
                      updated_at = excluded.updated_at
                    """,
                    (
                        word,
                        progress.due_at,
                        card_state,
                        progress.stability,
                        progress.difficulty,
                        review_count,
                        1 if progress.mastered else 0,
                        progress.last_shown_at,
                        progress.last_pronounced_at,
                        progress.last_expanded_at,
                        progress.last_reviewed_at,
                        progress.last_rating,
                        progress.show_count,
                        progress.known_count,
                        progress.unknown_count,
                        imported_at,
                        imported_at,
                    ),
                )

            for word in state.recent_words:
                conn.execute(
                    "INSERT INTO recent_words (word, shown_at) VALUES (?, ?)",
                    (word, imported_at),
                )

            self._set_app_state(conn, "legacy_learning_state_imported_at", imported_at)

    def get_card(self, word: str) -> StudyCard | None:
        normalized = word.strip()
        if not normalized:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                  id,
                  word,
                  due_at,
                  state,
                  stability,
                  difficulty,
                  reps,
                  lapses,
                  mastered,
                  suspended,
                  snoozed_until,
                  show_count,
                  known_count,
                  unknown_count,
                  fsrs_payload_json
                FROM cards
                WHERE word = ?
                """,
                (normalized,),
            ).fetchone()
        return _row_to_card(row) if row is not None else None

    def select_next_word(
        self,
        catalog_words: Sequence[WordEntry],
        *,
        now: datetime,
        recent_window_size: int = 5,
        rng: WeightedRandomSource | None = None,
    ) -> WordSelectionResult:
        app_snoozed_until = self._get_app_state("app_snoozed_until")
        if _is_after(app_snoozed_until, now):
            return WordSelectionResult(word=None, should_pause=True, notice_key="app_snoozed")

        words = tuple(catalog_words)
        if not words:
            return WordSelectionResult(word=None, should_pause=True, notice_key="empty_catalog")

        cards = self._cards_by_word(words)
        available_words = [
            word
            for word in words
            if _card_can_be_selected(cards.get(word.word.casefold()), now)
        ]
        if not available_words:
            return WordSelectionResult(word=None, should_pause=True, notice_key="all_mastered")

        due_pool = [
            word
            for word in available_words
            if _card_is_due(cards.get(word.word.casefold()), now)
        ]
        new_pool = [
            word
            for word in available_words
            if _card_is_new(cards.get(word.word.casefold()))
        ]
        base_pool = due_pool or new_pool or available_words
        recent_set = self._recent_word_set(max(0, recent_window_size))
        fresh_pool = [word for word in base_pool if word.word.casefold() not in recent_set]
        candidate_pool = fresh_pool or base_pool
        selected_word = _choose_by_learning_need(
            candidate_pool,
            cards,
            now,
            rng or random.Random(),
        )
        return WordSelectionResult(
            word=selected_word,
            should_pause=False,
            used_recent_fallback=not bool(fresh_pool),
        )

    def snooze_word(self, word: str, *, until: datetime) -> None:
        normalized = word.strip()
        if not normalized:
            return
        now = _now_iso()
        with self._connect() as conn:
            self._upsert_card(
                conn,
                normalized,
                snoozed_until=until.isoformat(),
                updated_at=now,
            )

    def snooze_app(self, *, until: datetime) -> None:
        with self._connect() as conn:
            self._set_app_state(conn, "app_snoozed_until", until.isoformat())

    def upsert_card_for_test(self, word: str, **fields: object) -> None:
        now = _now_iso()
        payload = {"updated_at": now, **fields}
        with self._connect() as conn:
            self._upsert_card(conn, word, **payload)

    def record_word_shown(self, word: str, *, shown_at: datetime) -> None:
        normalized = word.strip()
        if not normalized:
            return
        shown_at_iso = shown_at.isoformat()
        with self._connect() as conn:
            existing = self._card_row(conn, normalized)
            existing_card = _row_to_card(existing) if existing is not None else None
            self._upsert_card(
                conn,
                normalized,
                show_count=(existing_card.show_count if existing_card is not None else 0) + 1,
                last_shown_at=shown_at_iso,
                updated_at=shown_at_iso,
            )
            conn.execute(
                "INSERT INTO recent_words (word, shown_at) VALUES (?, ?)",
                (normalized, shown_at_iso),
            )

    def record_word_pronounced(self, word: str, *, pronounced_at: datetime) -> None:
        normalized = word.strip()
        if not normalized:
            return
        with self._connect() as conn:
            self._upsert_card(
                conn,
                normalized,
                last_pronounced_at=pronounced_at.isoformat(),
                updated_at=pronounced_at.isoformat(),
            )

    def record_word_expanded(self, word: str, *, expanded_at: datetime) -> None:
        normalized = word.strip()
        if not normalized:
            return
        with self._connect() as conn:
            self._upsert_card(
                conn,
                normalized,
                last_expanded_at=expanded_at.isoformat(),
                updated_at=expanded_at.isoformat(),
            )

    def mark_word_mastered(self, word: str) -> None:
        normalized = word.strip()
        if not normalized:
            return
        with self._connect() as conn:
            self._upsert_card(
                conn,
                normalized,
                mastered=1,
                updated_at=_now_iso(),
            )

    def review_word(
        self,
        word: str,
        rating: ProjectReviewRating,
        *,
        reviewed_at: datetime,
    ) -> StudyCard:
        normalized = word.strip()
        if not normalized:
            raise ValueError("word must be non-empty")

        with self._connect() as conn:
            existing = self._card_row(conn, normalized)
            existing_card = _row_to_card(existing) if existing is not None else None
            result = self._fsrs_service.review(
                existing_card.fsrs_payload_json if existing_card is not None else None,
                rating,
                reviewed_at=reviewed_at,
            )
            known_increment = 1 if rating is ProjectReviewRating.KNOWN else 0
            unknown_increment = 1 if rating is ProjectReviewRating.UNKNOWN else 0
            lapses_increment = 1 if rating is ProjectReviewRating.UNKNOWN else 0
            reps = (existing_card.reps if existing_card is not None else 0) + 1
            lapses = (existing_card.lapses if existing_card is not None else 0) + lapses_increment
            self._upsert_card(
                conn,
                normalized,
                due_at=result.due_at,
                state=result.state,
                stability=result.stability,
                difficulty=result.difficulty,
                reps=reps,
                lapses=lapses,
                last_reviewed_at=reviewed_at.isoformat(),
                last_rating=result.last_rating,
                known_count=(existing_card.known_count if existing_card is not None else 0) + known_increment,
                unknown_count=(existing_card.unknown_count if existing_card is not None else 0) + unknown_increment,
                fsrs_payload_json=result.fsrs_card_json,
                updated_at=_now_iso(),
            )
            updated = self._card_row(conn, normalized)
            assert updated is not None
            updated_card = _row_to_card(updated)
            conn.execute(
                """
                INSERT INTO review_log (
                  card_id,
                  word,
                  reviewed_at,
                  rating,
                  state_before,
                  state_after,
                  scheduled_days,
                  elapsed_days,
                  duration_ms,
                  fsrs_review_log_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    updated_card.id,
                    updated_card.word,
                    reviewed_at.isoformat(),
                    result.last_rating,
                    existing_card.state if existing_card is not None else None,
                    result.state,
                    result.scheduled_days,
                    result.elapsed_days,
                    None,
                    result.fsrs_review_log_json,
                ),
            )
            return updated_card

    def review_logs_for_test(self, word: str) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM review_log
                WHERE word = ?
                ORDER BY reviewed_at, id
                """,
                (word,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _get_app_state(self, key: str) -> str | None:
        if not self._db_path.exists():
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row is not None else None

    @staticmethod
    def _set_app_state(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO app_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (key, value, _now_iso()),
        )

    def _cards_by_word(self, words: Sequence[WordEntry]) -> dict[str, StudyCard]:
        raw_words = [word.word for word in words]
        if not raw_words:
            return {}
        placeholders = ", ".join("?" for _ in raw_words)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                  id,
                  word,
                  due_at,
                  state,
                  stability,
                  difficulty,
                  reps,
                  lapses,
                  mastered,
                  suspended,
                  snoozed_until,
                  show_count,
                  known_count,
                  unknown_count,
                  fsrs_payload_json
                FROM cards
                WHERE word IN ({placeholders})
                """,
                raw_words,
            ).fetchall()
        return {str(row["word"]).casefold(): _row_to_card(row) for row in rows}

    def _card_row(self, conn: sqlite3.Connection, word: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT
              id,
              word,
              due_at,
              state,
              stability,
              difficulty,
              reps,
              lapses,
              mastered,
              suspended,
              snoozed_until,
              show_count,
              known_count,
              unknown_count,
              fsrs_payload_json
            FROM cards
            WHERE word = ?
            """,
            (word,),
        ).fetchone()

    def _recent_word_set(self, limit: int) -> set[str]:
        if limit <= 0:
            return set()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT word
                FROM recent_words
                ORDER BY shown_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {str(row["word"]).casefold() for row in rows}

    def _upsert_card(self, conn: sqlite3.Connection, word: str, **fields: object) -> None:
        now = _now_iso()
        insert_payload = {
            "word": word,
            "due_at": None,
            "state": "new",
            "stability": None,
            "difficulty": None,
            "reps": 0,
            "lapses": 0,
            "mastered": 0,
            "suspended": 0,
            "snoozed_until": None,
            "last_shown_at": None,
            "last_pronounced_at": None,
            "last_expanded_at": None,
            "last_reviewed_at": None,
            "last_rating": None,
            "show_count": 0,
            "known_count": 0,
            "unknown_count": 0,
            "fsrs_payload_json": None,
            "created_at": now,
            "updated_at": now,
        }
        insert_payload.update(fields)
        columns = tuple(insert_payload)
        placeholders = ", ".join("?" for _ in columns)
        update_columns = tuple(
            column for column in fields if column not in {"word", "created_at"}
        )
        if "updated_at" not in update_columns:
            update_columns = (*update_columns, "updated_at")
        update_sql = ", ".join(f"{column} = excluded.{column}" for column in update_columns)
        conn.execute(
            f"""
            INSERT INTO cards ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(word) DO UPDATE SET {update_sql}
            """,
            tuple(insert_payload[column] for column in columns),
        )


def _row_to_card(row: sqlite3.Row) -> StudyCard:
    return StudyCard(
        id=int(row["id"]),
        word=str(row["word"]),
        due_at=row["due_at"],
        state=str(row["state"]),
        stability=_float_or_none(row["stability"]),
        difficulty=_float_or_none(row["difficulty"]),
        reps=int(row["reps"]),
        lapses=int(row["lapses"]),
        mastered=bool(row["mastered"]),
        suspended=bool(row["suspended"]),
        snoozed_until=row["snoozed_until"],
        show_count=int(row["show_count"]),
        known_count=int(row["known_count"]),
        unknown_count=int(row["unknown_count"]),
        fsrs_payload_json=row["fsrs_payload_json"],
    )


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_after(value: str | None, reference: datetime) -> bool:
    parsed = _parse_datetime(value)
    if parsed is None:
        return False
    return parsed > _as_utc(reference)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _card_can_be_selected(card: StudyCard | None, now: datetime) -> bool:
    if card is None:
        return True
    if card.mastered or card.suspended:
        return False
    return not _is_after(card.snoozed_until, now)


def _card_is_due(card: StudyCard | None, now: datetime) -> bool:
    if card is None:
        return False
    due_at = _parse_datetime(card.due_at)
    return due_at is not None and due_at <= _as_utc(now)


def _card_is_new(card: StudyCard | None) -> bool:
    return card is None or card.state == "new"


def _choose_by_learning_need(
    words: list[WordEntry],
    cards: dict[str, StudyCard],
    now: datetime,
    rng: WeightedRandomSource,
) -> WordEntry:
    if len(words) == 1:
        return words[0]
    weights = [
        _learning_need_weight(cards.get(word.word.casefold()), now)
        for word in words
    ]
    return rng.choices(words, weights=weights, k=1)[0]


def _learning_need_weight(card: StudyCard | None, now: datetime) -> float:
    if card is None:
        return 3.0

    weight = 1.0
    due_at = _parse_datetime(card.due_at)
    if due_at is not None:
        overdue_hours = max(0.0, (_as_utc(now) - due_at).total_seconds() / 3600.0)
        weight += min(24.0, overdue_hours / 2.0)
    if card.state == "new":
        weight += 2.0
    if card.difficulty is not None:
        weight += max(0.0, min(9.0, card.difficulty - 1.0))
    if card.stability is not None:
        weight += max(0.0, 3.0 - min(3.0, card.stability))
    weight += min(10.0, card.lapses * 1.5)
    weight += min(8.0, card.unknown_count)
    weight += min(2.0, 2.0 / max(1, card.show_count + 1))
    return max(0.1, weight)
