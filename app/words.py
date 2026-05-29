from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import LearningState, WordEntry, WordSelectionResult, WordbookIssue

DEFAULT_WORDBOOK_FILENAME = "kaoyan_core.json"
DEFAULT_RECENT_WORDS_WINDOW = 5

DEFAULT_WORDBOOK_ENTRIES: tuple[dict[str, object], ...] = (
    {
        "word": "abandon",
        "ipa": "/əˈbændən/",
        "part_of_speech": "verb",
        "definitions": ["放弃", "抛弃"],
        "example_sentence": "Many exam takers refuse to abandon their daily review plan.",
        "example_translation": "很多考研学生不会放弃每天的复习计划。",
    },
    {
        "word": "allocate",
        "ipa": "/ˈæləkeɪt/",
        "part_of_speech": "verb",
        "definitions": ["分配", "拨给"],
        "example_sentence": "She learned to allocate two focused hours to vocabulary revision.",
        "example_translation": "她学会了给词汇复习分配两个专注小时。",
    },
    {
        "word": "compile",
        "ipa": "/kəmˈpaɪl/",
        "part_of_speech": "verb",
        "definitions": ["汇编", "整理"],
        "example_sentence": "He compiled a notebook of confusing words before the mock exam.",
        "example_translation": "他在模拟考试前整理了一本易混词笔记。",
    },
    {
        "word": "constrain",
        "ipa": "/kənˈstreɪn/",
        "part_of_speech": "verb",
        "definitions": ["限制", "约束"],
        "example_sentence": "A tight schedule can constrain how much reading you finish each week.",
        "example_translation": "紧张的安排会限制你每周能完成的阅读量。",
    },
    {
        "word": "derive",
        "ipa": "/dɪˈraɪv/",
        "part_of_speech": "verb",
        "definitions": ["获得", "推导"],
        "example_sentence": "You can derive the main idea by tracking repeated arguments in the passage.",
        "example_translation": "通过追踪文章中的重复论点，你可以推导出中心思想。",
    },
    {
        "word": "eliminate",
        "ipa": "/ɪˈlɪmɪneɪt/",
        "part_of_speech": "verb",
        "definitions": ["排除", "消除"],
        "example_sentence": "Smart note-taking helps eliminate careless mistakes in translation questions.",
        "example_translation": "高质量笔记能帮助你减少翻译题里的粗心错误。",
    },
    {
        "word": "formula",
        "ipa": "/ˈfɔːrmjələ/",
        "part_of_speech": "noun",
        "definitions": ["公式", "准则"],
        "example_sentence": "There is no fixed formula for remembering every unfamiliar collocation.",
        "example_translation": "记住每个陌生搭配并没有固定公式。",
    },
    {
        "word": "generate",
        "ipa": "/ˈdʒenəreɪt/",
        "part_of_speech": "verb",
        "definitions": ["产生", "引起"],
        "example_sentence": "Daily recitation can generate steady progress over a long preparation cycle.",
        "example_translation": "每天背诵能在漫长备考周期里产生稳定进步。",
    },
    {
        "word": "hypothesis",
        "ipa": "/haɪˈpɑːθəsɪs/",
        "part_of_speech": "noun",
        "definitions": ["假设"],
        "example_sentence": "The author tests one hypothesis after another in the final section.",
        "example_translation": "作者在最后一部分逐一检验各个假设。",
    },
    {
        "word": "justify",
        "ipa": "/ˈdʒʌstɪfaɪ/",
        "part_of_speech": "verb",
        "definitions": ["证明合理", "为……辩护"],
        "example_sentence": "You must justify every answer choice with evidence from the passage.",
        "example_translation": "你必须用原文证据来证明每个选项的合理性。",
    },
    {
        "word": "mediate",
        "ipa": "/ˈmiːdieɪt/",
        "part_of_speech": "verb",
        "definitions": ["调节", "传递影响"],
        "example_sentence": "Context often mediates the meaning of an unfamiliar academic term.",
        "example_translation": "语境常常会调节陌生学术词汇的含义。",
    },
    {
        "word": "retain",
        "ipa": "/rɪˈteɪn/",
        "part_of_speech": "verb",
        "definitions": ["保留", "记住"],
        "example_sentence": "Short review loops help you retain new words for the long term.",
        "example_translation": "短周期复习能帮助你长期记住新单词。",
    },
)


@dataclass(slots=True, frozen=True)
class WordCatalog:
    words: tuple[WordEntry, ...]
    by_word: dict[str, WordEntry]

    @classmethod
    def from_entries(cls, entries: Iterable[WordEntry]) -> "WordCatalog":
        ordered = tuple(sorted(entries, key=lambda item: item.word.casefold()))
        return cls(
            words=ordered,
            by_word={item.word.casefold(): item for item in ordered},
        )


@dataclass(slots=True, frozen=True)
class WordCatalogLoadResult:
    catalog: WordCatalog
    issues: list[WordbookIssue]
    recovered_with_default: bool = False


def ensure_default_wordbook(wordbooks_dir: Path) -> Path:
    wordbooks_dir.mkdir(parents=True, exist_ok=True)
    default_path = wordbooks_dir / DEFAULT_WORDBOOK_FILENAME
    if default_path.exists():
        return default_path

    default_path.write_text(
        json.dumps(DEFAULT_WORDBOOK_ENTRIES, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return default_path


def load_word_catalog(wordbooks_dir: Path) -> WordCatalogLoadResult:
    first_pass = _load_word_catalog_once(wordbooks_dir)
    if first_pass.catalog.words:
        return first_pass

    ensure_default_wordbook(wordbooks_dir)
    second_pass = _load_word_catalog_once(wordbooks_dir)
    return WordCatalogLoadResult(
        catalog=second_pass.catalog,
        issues=[*first_pass.issues, *second_pass.issues],
        recovered_with_default=bool(second_pass.catalog.words),
    )


def select_next_word(
    catalog: WordCatalog,
    learning_state: LearningState | None = None,
    *,
    recent_words: list[str] | None = None,
    recent_window_size: int = DEFAULT_RECENT_WORDS_WINDOW,
    rng: random.Random | None = None,
) -> WordSelectionResult:
    state = learning_state or LearningState()
    unmastered_pool = [
        item
        for item in catalog.words
        if not state.progress.get(item.word, state.progress.get(item.word.casefold(), None)) or not _is_mastered(state, item.word)
    ]
    if not unmastered_pool:
        return WordSelectionResult(word=None, should_pause=True, notice_key="all_mastered")

    recent_history = recent_words if recent_words is not None else state.recent_words
    normalized_recent = [item.casefold() for item in recent_history[-max(0, recent_window_size):]]
    recent_set = set(normalized_recent)
    fresh_pool = [item for item in unmastered_pool if item.word.casefold() not in recent_set]
    candidate_pool = fresh_pool or unmastered_pool

    chooser = rng or random.Random()
    selected = chooser.choice(candidate_pool)
    return WordSelectionResult(
        word=selected,
        should_pause=False,
        notice_key=None,
        used_recent_fallback=not bool(fresh_pool),
    )


def _load_word_catalog_once(wordbooks_dir: Path) -> WordCatalogLoadResult:
    if not wordbooks_dir.exists():
        return WordCatalogLoadResult(catalog=WordCatalog.from_entries(()), issues=[])

    merged: dict[str, WordEntry] = {}
    issues: list[WordbookIssue] = []

    for path in sorted(wordbooks_dir.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            issues.append(WordbookIssue(source=str(path), message=f"{type(exc).__name__}: {exc}"))
            continue

        if not isinstance(payload, list):
            issues.append(WordbookIssue(source=str(path), message="Wordbook root must be a JSON array."))
            continue

        for index, raw_entry in enumerate(payload):
            try:
                entry = _parse_word_entry(raw_entry)
            except ValueError as exc:
                issues.append(WordbookIssue(source=str(path), message=f"Entry {index}: {exc}"))
                continue

            merged[entry.word.casefold()] = entry

    return WordCatalogLoadResult(catalog=WordCatalog.from_entries(merged.values()), issues=issues)


def _parse_word_entry(raw_entry: object) -> WordEntry:
    if not isinstance(raw_entry, dict):
        raise ValueError("Word entry must be an object.")

    required = (
        "word",
        "ipa",
        "part_of_speech",
        "definitions",
        "example_sentence",
        "example_translation",
    )
    missing = [field for field in required if field not in raw_entry]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    definitions_raw = raw_entry["definitions"]
    if not isinstance(definitions_raw, list) or not definitions_raw:
        raise ValueError("definitions must be a non-empty array of strings.")

    definitions = [_require_non_empty_string(item, "definitions[]") for item in definitions_raw]
    return WordEntry(
        word=_require_non_empty_string(raw_entry["word"], "word"),
        ipa=_require_non_empty_string(raw_entry["ipa"], "ipa"),
        part_of_speech=_require_non_empty_string(raw_entry["part_of_speech"], "part_of_speech"),
        definitions=definitions,
        example_sentence=_require_non_empty_string(raw_entry["example_sentence"], "example_sentence"),
        example_translation=_require_non_empty_string(
            raw_entry["example_translation"],
            "example_translation",
        ),
    )


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _is_mastered(state: LearningState, word: str) -> bool:
    progress = state.progress.get(word)
    if progress is None:
        progress = state.progress.get(word.casefold())
    return progress.mastered if progress is not None else False
