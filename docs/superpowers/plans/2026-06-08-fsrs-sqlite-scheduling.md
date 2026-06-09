# FSRS SQLite Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the full-file JSON learning state with SQLite-backed card state and FSRS review scheduling while preserving the lightweight tray popup experience.

**Architecture:** Keep `SchedulerCore` responsible for desktop interruption cadence and move memory scheduling into a SQLite repository plus an FSRS adapter. `AppController` continues to coordinate UI actions, but persistence flows through repository methods instead of mutating an in-memory `LearningState` and saving the whole JSON file.

**Tech Stack:** Python 3.11, PySide6, SQLite `sqlite3`, fsrs `>=6,<7`, pytest

---

## 当前执行状态

截至 2026-06-08：

| 范围 | 状态 | 证据 |
| --- | --- | --- |
| FSRS 适配层 | 已实现 | `app/fsrs_service.py`，`tests/test_fsrs_service.py` |
| SQLite schema、旧 JSON 导入、选词、稍后、全局暂停和复习日志 | 已实现 | `app/study_store.py`，`tests/test_study_store.py` |
| controller 接入 | 已实现 | `app/controller.py`，`tests/test_controller.py` |
| 弹窗“稍后”和托盘“暂停 30 分钟”入口 | 已实现 | `app/overlays/`、`app/tray.py`，`tests/test_overlays.py` |
| 设置页稍后时长 | 已实现 | `app/settings.py`、`app/settings_window.py`，`tests/test_settings.py` |
| 完整逻辑测试 | 已通过 | `py -3.11 -m pytest tests -q`：66 passed |
| Windows 真实托盘/弹窗/热键/TTS 运行检查 | 未执行 | 需要启动 `py -3.11 main.py` 并人工检查 |
| PyInstaller 打包检查 | 未执行 | 需要运行 `.\build\build_exe.ps1` |

下方 checkbox 保留为原始执行配方；其中“先运行并确认失败”的 TDD 步骤不应在事后被当成已执行证据。当前实现事实以源码、测试和本节状态表为准。

---

## 稳定文档归属

本计划是 dated implementation plan。执行前先阅读：

- `docs/architecture/module-boundaries.md`
- `docs/specs/app-controller.md`
- `docs/specs/settings-and-storage.md`
- `docs/specs/study-scheduling.md`
- `docs/specs/popup-overlays.md`
- `docs/specs/tray-hotkeys-tts.md`
- `docs/specs/packaging-runtime.md`

实现过程中如契约变化，优先更新对应模块 spec，再同步本计划中仍有用的执行细节。

## 文件结构

- Create: `app/study_store.py`  
  Owns SQLite connection setup, schema migrations, card queries, recent words, app snooze state, legacy JSON import, and write operations for show/pronounce/expand/master/snooze.
- Create: `app/fsrs_service.py`  
  Wraps the third-party `fsrs` package and exposes project-level methods for applying `known` and `unknown` reviews.
- Modify: `app/controller.py`  
  Replace direct `LearningStateStore` usage with `StudyStore`; route known/unknown/snooze/close/mastered actions through repository methods.
- Modify: `app/words.py`  
  Split content selection from learning-state filtering where needed, or add a repository-backed selection helper while keeping wordbook loading unchanged.
- Modify: `app/models.py`  
  Add small project dataclasses/enums for card state, review rating, and selection results if the repository needs typed return values.
- Modify: `app/settings.py`  
  Keep `LearningStateStore` only for legacy import compatibility or move legacy normalization into `study_store.py`; do not remove compatibility in the first migration.
- Modify: `app/settings_window.py`, `app/overlays/card_popup.py`, `app/overlays/barrage_popup.py`, `app/tray.py`  
  Add lightweight "稍后" and "暂停 30 分钟" UI actions after persistence works.
- Modify: `requirements.txt`  
  Add `fsrs>=6,<7`.
- Create: `tests/test_study_store.py`  
  Covers schema, migration, selection, snooze, and repository writes.
- Create: `tests/test_fsrs_service.py`  
  Covers known/unknown mapping to FSRS and adapter output shape.
- Modify: `tests/test_controller.py`, `tests/test_words.py`, `tests/test_settings.py`, `tests/test_review.py`  
  Update expectations from JSON `LearningState` to SQLite repository behavior while keeping legacy tests where useful.
- Modify: `README.md`, `docs/specs/runtime-and-data-contracts.md`, `memory/03-handoff.md`  
  Document the new SQLite file, migration behavior, verification limits, and update any affected module spec after implementation.

## 任务表

| 任务 | 目标 | 主要文件 | 验证 |
| --- | --- | --- | --- |
| 1 | 添加依赖与 FSRS 适配层测试 | `requirements.txt`, `app/fsrs_service.py`, `tests/test_fsrs_service.py` | `py -3.11 -m pytest tests/test_fsrs_service.py -q` |
| 2 | 建立 SQLite schema 与迁移框架 | `app/study_store.py`, `tests/test_study_store.py` | `py -3.11 -m pytest tests/test_study_store.py -q` |
| 3 | 导入旧 JSON 学习状态 | `app/study_store.py`, `app/settings.py`, `tests/test_study_store.py` | legacy import tests pass |
| 4 | 实现 repository 选词与近期避让 | `app/study_store.py`, `app/words.py`, `tests/test_study_store.py` | due/new/recent/snooze tests pass |
| 5 | 实现 FSRS 正式复习写入 | `app/fsrs_service.py`, `app/study_store.py`, `tests/test_study_store.py` | review log tests pass |
| 6 | 接入 controller 的展示和复习流 | `app/controller.py`, `tests/test_controller.py` | controller tests pass |
| 7 | 添加“稍后”和全局暂停 UI 入口 | overlays, tray, settings UI | targeted UI/controller tests pass |
| 8 | 文档和完整验证 | README, docs/specs, memory | full pytest and Windows runtime notes |

### Task 1: FSRS adapter contract

**Files:**
- Modify: `requirements.txt`
- Create: `app/fsrs_service.py`
- Create: `tests/test_fsrs_service.py`

- [ ] **Step 1: Add the FSRS dependency**

Update `requirements.txt` to include:

```text
fsrs>=6,<7
```

- [ ] **Step 2: Write adapter tests**

Create `tests/test_fsrs_service.py` with tests for project-level ratings:

```python
from __future__ import annotations

from datetime import UTC, datetime

from app.fsrs_service import FsrsReviewService, ProjectReviewRating


def test_known_review_maps_to_good_and_returns_due_state() -> None:
    service = FsrsReviewService()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)

    result = service.review(None, ProjectReviewRating.KNOWN, reviewed_at=now)

    assert result.last_rating == "known"
    assert result.due_at is not None
    assert result.stability is None or result.stability >= 0
    assert result.difficulty is None or result.difficulty > 0
    assert result.fsrs_card_json
    assert result.fsrs_review_log_json


def test_unknown_review_maps_to_again_and_returns_due_state() -> None:
    service = FsrsReviewService()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)

    result = service.review(None, ProjectReviewRating.UNKNOWN, reviewed_at=now)

    assert result.last_rating == "unknown"
    assert result.due_at is not None
    assert result.fsrs_card_json
    assert result.fsrs_review_log_json
```

- [ ] **Step 3: Run the adapter tests and confirm they fail**

Run:

```powershell
py -3.11 -m pytest tests/test_fsrs_service.py -q
```

Expected: fail because `app.fsrs_service` does not exist.

- [ ] **Step 4: Implement the adapter**

Create `app/fsrs_service.py` with a narrow wrapper. If the installed FSRS API differs, keep the public project API below and adjust only inside this file.

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from fsrs import Card, Rating, Scheduler


class ProjectReviewRating(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class FsrsReviewResult:
    due_at: str | None
    state: str
    stability: float | None
    difficulty: float | None
    scheduled_days: int | None
    elapsed_days: int | None
    last_rating: str
    fsrs_card_json: str
    fsrs_review_log_json: str


class FsrsReviewService:
    def __init__(self, scheduler: Scheduler | None = None) -> None:
        self._scheduler = scheduler or Scheduler()

    def review(
        self,
        fsrs_card_json: str | None,
        rating: ProjectReviewRating,
        *,
        reviewed_at: datetime,
    ) -> FsrsReviewResult:
        card = self._load_card(fsrs_card_json)
        fsrs_rating = Rating.Good if rating is ProjectReviewRating.KNOWN else Rating.Again
        card, review_log = self._scheduler.review_card(card, fsrs_rating, reviewed_at)
        card_payload = card.to_dict()
        log_payload = review_log.to_dict()
        return FsrsReviewResult(
            due_at=_iso_or_none(card_payload.get("due")),
            state=str(card_payload.get("state", "")),
            stability=_float_or_none(card_payload.get("stability")),
            difficulty=_float_or_none(card_payload.get("difficulty")),
            scheduled_days=_int_or_none(log_payload.get("scheduled_days")),
            elapsed_days=_int_or_none(log_payload.get("elapsed_days")),
            last_rating=rating.value,
            fsrs_card_json=json.dumps(card_payload, ensure_ascii=False, sort_keys=True),
            fsrs_review_log_json=json.dumps(log_payload, ensure_ascii=False, sort_keys=True),
        )

    @staticmethod
    def _load_card(payload: str | None) -> Card:
        if not payload:
            return Card()
        return Card.from_dict(json.loads(payload))


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 5: Run adapter tests**

Run:

```powershell
py -3.11 -m pytest tests/test_fsrs_service.py -q
```

Expected: adapter tests pass. If the FSRS API differs, update only `app/fsrs_service.py` and keep tests focused on project behavior.

### Task 2: SQLite schema and repository skeleton

**Files:**
- Create: `app/study_store.py`
- Create: `tests/test_study_store.py`

- [ ] **Step 1: Write schema initialization tests**

Create `tests/test_study_store.py` with:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

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
```

- [ ] **Step 2: Run the schema test and confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_study_store.py::test_initializes_schema_idempotently -q
```

Expected: fail because `StudyStore` does not exist.

- [ ] **Step 3: Implement schema initialization**

Create `app/study_store.py` with `StudyStore.initialize()` using the schema from the design spec. Use `sqlite3.connect()`, `PRAGMA foreign_keys = ON`, and `CREATE TABLE IF NOT EXISTS`.

- [ ] **Step 4: Run schema test**

Run:

```powershell
py -3.11 -m pytest tests/test_study_store.py::test_initializes_schema_idempotently -q
```

Expected: pass.

### Task 3: Legacy JSON import

**Files:**
- Modify: `app/study_store.py`
- Modify: `tests/test_study_store.py`

- [ ] **Step 1: Write legacy import test**

Add a test that writes a legacy `learning_state.json` with one progress item and imports it:

```python
import json


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
```

- [ ] **Step 2: Run import test and confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_study_store.py::test_imports_legacy_learning_state_without_deleting_file -q
```

Expected: fail because import and `get_card()` are not implemented.

- [ ] **Step 3: Implement legacy import**

Add repository dataclasses and methods:

```python
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
```

Add `StudyStore.import_legacy_learning_state(legacy_path)` to read the legacy file, normalize it with `normalize_learning_state()`, upsert one `cards` row per progress entry, insert `recent_words`, and write `app_state.legacy_learning_state_imported_at`.

Add `StudyStore.get_card(word)` to return `StudyCard` for an existing row or `None` when the word has no row.

Use existing `normalize_learning_state()` from `app.settings` so corrupted or partial payloads follow current normalization rules.

- [ ] **Step 4: Run import tests**

Run:

```powershell
py -3.11 -m pytest tests/test_study_store.py -q
```

Expected: schema and import tests pass.

### Task 4: Repository-backed selection and snooze filtering

**Files:**
- Modify: `app/study_store.py`
- Modify: `tests/test_study_store.py`

- [ ] **Step 1: Write selection tests**

Add tests for due priority, new fallback, recent avoidance, card snooze, and global snooze:

```python
from datetime import UTC, datetime, timedelta

from app.models import WordEntry


def _entry(word: str) -> WordEntry:
    return WordEntry(
        word=word,
        ipa="/test/",
        part_of_speech="n.",
        definitions=[word],
        example_sentence=word,
        example_translation=word,
    )


def test_selects_due_card_before_new_word(tmp_path: Path) -> None:
    store = StudyStore(tmp_path / "oh_my_word.sqlite3")
    store.initialize()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)
    store.upsert_card_for_test("brisk", due_at=(now - timedelta(minutes=1)).isoformat())

    result = store.select_next_word([_entry("abandon"), _entry("brisk")], now=now)

    assert result.word is not None
    assert result.word.word == "brisk"


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
```

- [ ] **Step 2: Run selection tests and confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_study_store.py -q
```

Expected: fail because selection and snooze methods are missing.

- [ ] **Step 3: Implement selection and snooze**

Add `StudyStore.select_next_word(catalog_words, now, recent_window_size=5)` to return the existing `WordSelectionResult` type. Selection order must match the design spec: due, then new, then unmastered old cards, with recent avoidance inside the selected pool.

Add `StudyStore.snooze_word(word, until)` to upsert the card row and set `snoozed_until`.

Add `StudyStore.snooze_app(until)` to write `app_state.app_snoozed_until`.

Add `StudyStore.upsert_card_for_test(word, **fields)` as a test helper that upserts a row using explicit column names from the `cards` schema.

- [ ] **Step 4: Run selection tests**

Run:

```powershell
py -3.11 -m pytest tests/test_study_store.py -q
```

Expected: repository tests pass.

### Task 5: FSRS review writes and review log

**Files:**
- Modify: `app/study_store.py`
- Modify: `app/fsrs_service.py`
- Modify: `tests/test_study_store.py`

- [ ] **Step 1: Write review persistence tests**

Add tests:

```python
from app.fsrs_service import FsrsReviewService, ProjectReviewRating


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
```

- [ ] **Step 2: Run review persistence tests and confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_study_store.py -q
```

Expected: fail because review persistence is missing.

- [ ] **Step 3: Implement review persistence**

Add `StudyStore.review_word(word, rating, reviewed_at)` to load the existing FSRS payload, call `FsrsReviewService.review()`, update the card counters and FSRS fields, insert one `review_log` row, and return the updated `StudyCard`.

Add `StudyStore.review_logs_for_test(word)` as a test helper returning review log rows ordered by `reviewed_at`.

Use a transaction so the card update and `review_log` insert succeed or fail together.

- [ ] **Step 4: Run repository and adapter tests**

Run:

```powershell
py -3.11 -m pytest tests/test_fsrs_service.py tests/test_study_store.py -q
```

Expected: all FSRS and study store tests pass.

### Task 6: Controller integration

**Files:**
- Modify: `app/controller.py`
- Modify: `tests/test_controller.py`
- Modify: `app/settings.py`

- [ ] **Step 1: Write controller tests for repository calls**

Update controller tests with fakes that assert:

- `_request_fresh_word()` asks `StudyStore.select_next_word()`.
- `_show_word()` records show through `StudyStore.record_word_shown()`.
- `review_current_word(known=True)` calls `StudyStore.review_word()` with the current word and `ProjectReviewRating.KNOWN`.
- `review_current_word(known=False)` calls `StudyStore.review_word()` with the current word and `ProjectReviewRating.UNKNOWN`.
- `snooze_visible_popup()` calls `StudyStore.snooze_word()`.

- [ ] **Step 2: Run controller tests and confirm failure**

Run:

```powershell
py -3.11 -m pytest tests/test_controller.py -q
```

Expected: fail because controller still uses `LearningStateStore`.

- [ ] **Step 3: Replace controller persistence wiring**

In `AppController.initialize()`:

- Create `StudyStore(self._paths.storage_dir / "oh_my_word.sqlite3", logger=self.logger)`.
- Call `initialize()`.
- Call `import_legacy_learning_state(self._paths.learning_state_path)`.
- Remove runtime dependency on `LearningStateStore.load()` for active scheduling.

Update `_request_fresh_word()`, `_show_word()`, `pronounce_current_word()`, `toggle_details()`, `mark_current_word_mastered()`, and `review_current_word()` to call repository methods.

- [ ] **Step 4: Run controller tests**

Run:

```powershell
py -3.11 -m pytest tests/test_controller.py tests/test_study_store.py tests/test_fsrs_service.py -q
```

Expected: targeted tests pass.

### Task 7: Lightweight snooze UI and actions

**Files:**
- Modify: `app/models.py`
- Modify: `app/settings.py`
- Modify: `app/settings_window.py`
- Modify: `app/tray.py`
- Modify: `app/overlays/card_popup.py`
- Modify: `app/overlays/barrage_popup.py`
- Modify: `app/controller.py`
- Modify: `tests/test_settings.py`
- Modify: `tests/test_controller.py`
- Modify: `tests/test_overlays.py`

- [ ] **Step 1: Add tests for snooze settings and actions**

Add tests that default `snooze_minutes` is 30, popup snooze no-ops when no popup is visible, popup snooze updates the current word, and tray pause writes global app snooze state.

- [ ] **Step 2: Add model and settings fields**

Add:

```python
DEFAULT_SNOOZE_MINUTES = 30
```

Add `snooze_minutes: int = DEFAULT_SNOOZE_MINUTES` to `AppSettings`, normalize it as a positive integer, persist it in `settings_to_dict()`, and expose it in settings UI as a spin box labeled `稍后时长`.

- [ ] **Step 3: Add overlay button signal**

Add a `snoozed = Signal(str)` or reuse a controller-level method from a "稍后" button. The button should be visible next to `认识` and `不认识`.

- [ ] **Step 4: Add controller methods**

Add `AppController.snooze_visible_popup()` for the current popup word and `AppController.snooze_app_for_default_duration()` for global pause. Current popup snooze calls `StudyStore.snooze_word()`. Global tray pause calls `StudyStore.snooze_app()`.

- [ ] **Step 5: Add tray menu action**

Add a tray action labeled `暂停 30 分钟`. It calls the controller global snooze method and closes any active popup.

- [ ] **Step 6: Run targeted UI/controller tests**

Run:

```powershell
py -3.11 -m pytest tests/test_settings.py tests/test_controller.py tests/test_overlays.py -q
```

Expected: targeted tests pass.

### Task 8: Documentation, verification, and runtime check

**Files:**
- Modify: `README.md`
- Modify: `docs/specs/runtime-and-data-contracts.md`
- Modify: `docs/specs/settings-and-storage.md`
- Modify: `docs/specs/study-scheduling.md`
- Modify: `docs/specs/popup-overlays.md`
- Modify: `docs/specs/tray-hotkeys-tts.md`
- Modify: `docs/specs/packaging-runtime.md`
- Modify: `memory/03-handoff.md`

- [ ] **Step 1: Update stable docs**

Document:

- `storage/oh_my_word.sqlite3`
- Legacy `storage/learning_state.json` import behavior
- FSRS `认识`/`不认识` mapping
- `稍后` does not write review log
- `settings.json` remains settings-only

- [ ] **Step 2: Run full test suite**

Run:

```powershell
py -3.11 -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Windows app check**

Run:

```powershell
py -3.11 main.py
```

Check:

- App starts from tray.
- Existing settings load.
- Legacy JSON import does not delete `storage/learning_state.json`.
- A word can be shown manually.
- `认识` and `不认识` close the popup and persist card state.
- `稍后` closes the popup and does not create review log.
- `暂停 30 分钟` prevents immediate automatic popups.

- [ ] **Step 4: Decide whether to build package**

If this change is intended for distribution, run:

```powershell
.\build\build_exe.ps1
```

Expected: PyInstaller writes a fresh `dist/oh-my-word-py` output. If package runtime is in scope, launch the built executable and repeat the smoke checks.

## 自查

- Spec coverage: covered SQLite storage, FSRS mapping, two-button UI, current-card snooze, global snooze, migration, selection, testing, and runtime verification.
- Placeholder scan: no unfinished marker phrases or vague edge-case steps remain.
- Type consistency: plan uses `StudyStore`, `FsrsReviewService`, `ProjectReviewRating`, `StudyCard`, and existing `WordSelectionResult` consistently.
