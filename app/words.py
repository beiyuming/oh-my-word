from __future__ import annotations

import csv
import json
import random
from urllib.error import URLError
from urllib.request import urlopen
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .models import LearningState, WordEntry, WordSelectionResult, WordbookIssue
from .review import is_due

DEFAULT_WORDBOOK_FILENAME = "kaoyan_core.json"
DEFAULT_RECENT_WORDS_WINDOW = 5
RECOMMENDED_KAOYAN_SOURCE_URL = (
    "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json"
)
RECOMMENDED_KAOYAN_SOURCE_PAGE = "https://github.com/exam-data/NETEMVocabulary"
RECOMMENDED_KAOYAN_LICENSE = "CC BY-NC-SA 4.0"

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


@dataclass(slots=True, frozen=True)
class WordbookImportResult:
    path: Path
    imported_count: int


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


def import_wordbook_file(source_path: Path, wordbooks_dir: Path) -> WordbookImportResult:
    if not source_path.exists() or not source_path.is_file():
        raise ValueError("请选择一个存在的词库文件。")

    suffix = source_path.suffix.casefold()
    if suffix == ".json":
        entries = _load_import_json(source_path)
    elif suffix == ".csv":
        entries = _load_import_csv(source_path)
    else:
        raise ValueError("仅支持导入 JSON 或 CSV 词库。")

    if not entries:
        raise ValueError("词库里没有可导入的单词。")

    wordbooks_dir.mkdir(parents=True, exist_ok=True)
    target = _available_import_path(wordbooks_dir, source_path.stem)
    target.write_text(
        json.dumps([_word_entry_to_dict(entry) for entry in entries], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return WordbookImportResult(path=target, imported_count=len(entries))


def download_recommended_kaoyan_wordbook(wordbooks_dir: Path) -> WordbookImportResult:
    try:
        with urlopen(RECOMMENDED_KAOYAN_SOURCE_URL, timeout=20) as response:
            raw_bytes = response.read()
    except (OSError, URLError) as exc:
        raise ValueError(f"下载推荐词库失败：{exc}") from exc

    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"推荐词库格式无法解析：{exc}") from exc

    if isinstance(payload, dict):
        for key in ("words", "data", "entries", "items"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            list_values = [value for value in payload.values() if isinstance(value, list)]
            if len(list_values) == 1:
                payload = list_values[0]
    if not isinstance(payload, list):
        raise ValueError("推荐词库格式不是单词数组。")

    entries = _parse_import_entries(payload)
    if not entries:
        raise ValueError("推荐词库里没有可导入的单词。")

    wordbooks_dir.mkdir(parents=True, exist_ok=True)
    target = wordbooks_dir / "kaoyan_full.json"
    target.write_text(
        json.dumps([_word_entry_to_dict(entry) for entry in entries], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return WordbookImportResult(path=target, imported_count=len(entries))


def select_next_word(
    catalog: WordCatalog,
    learning_state: LearningState | None = None,
    *,
    recent_words: list[str] | None = None,
    recent_window_size: int = DEFAULT_RECENT_WORDS_WINDOW,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> WordSelectionResult:
    state = learning_state or LearningState()
    reference_time = now or datetime.now(UTC)
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
    due_pool = [
        item
        for item in unmastered_pool
        if _is_due_for_review(state, item.word, reference_time)
    ]
    new_pool = [
        item
        for item in unmastered_pool
        if _progress_for_word(state, item.word) is None
    ]
    base_pool = due_pool or new_pool or unmastered_pool
    fresh_pool = [item for item in base_pool if item.word.casefold() not in recent_set]
    candidate_pool = fresh_pool or base_pool

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


def _load_import_json(path: Path) -> list[WordEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 JSON：{exc}") from exc

    raw_entries = payload
    if isinstance(payload, dict):
        for key in ("words", "data", "entries", "items"):
            if isinstance(payload.get(key), list):
                raw_entries = payload[key]
                break
        else:
            list_values = [value for value in payload.values() if isinstance(value, list)]
            if len(list_values) == 1:
                raw_entries = list_values[0]
    if not isinstance(raw_entries, list):
        raise ValueError("JSON 词库根节点需要是数组，或包含 words/data/entries/items 数组。")

    return _parse_import_entries(raw_entries)


def _load_import_csv(path: Path) -> list[WordEntry]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise ValueError(f"无法读取 CSV：{exc}") from exc
    if not rows:
        return []
    return _parse_import_entries(rows)


def _parse_import_entries(raw_entries: Iterable[object]) -> list[WordEntry]:
    entries: dict[str, WordEntry] = {}
    for raw_entry in raw_entries:
        entry = _parse_flexible_word_entry(raw_entry)
        if entry is not None:
            entries[entry.word.casefold()] = entry
    return sorted(entries.values(), key=lambda item: item.word.casefold())


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


def _parse_flexible_word_entry(raw_entry: object) -> WordEntry | None:
    if not isinstance(raw_entry, dict):
        return None

    flattened = _flatten_import_entry(raw_entry)
    word = _first_import_text(
        flattened,
        "word",
        "term",
        "name",
        "headword",
        "headWord",
        "wordHead",
        "wordRank",
        "text",
        "单词",
    )
    if not word:
        return None

    definitions = _first_import_lines(
        flattened,
        "definitions",
        "definition",
        "definitionCn",
        "translations",
        "translation",
        "meaning",
        "meanings",
        "trans",
        "tran",
        "tranCn",
        "chinese",
        "cn",
        "desc",
        "释义",
    )
    if not definitions:
        return None

    ipa = _first_import_text(flattened, "ipa", "phonetic", "pronunciation", "ukphone", "usphone", "音标") or "/.../"
    part_of_speech = _first_import_text(flattened, "part_of_speech", "pos", "tag", "speech", "词性") or "unknown"
    example_sentence = _first_import_text(flattened, "example_sentence", "example", "sentence", "sent", "例句") or word
    example_translation = _first_import_text(
        flattened,
        "example_translation",
        "example_cn",
        "sentence_translation",
        "translation_example",
        "sentCn",
        "exampleTranslation",
        "例句翻译",
    ) or "暂无例句翻译。"

    return WordEntry(
        word=word,
        ipa=ipa,
        part_of_speech=part_of_speech,
        definitions=definitions,
        example_sentence=example_sentence,
        example_translation=example_translation,
    )


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _word_entry_to_dict(entry: WordEntry) -> dict[str, object]:
    return {
        "word": entry.word,
        "ipa": entry.ipa,
        "part_of_speech": entry.part_of_speech,
        "definitions": list(entry.definitions),
        "example_sentence": entry.example_sentence,
        "example_translation": entry.example_translation,
    }


def _available_import_path(wordbooks_dir: Path, source_stem: str) -> Path:
    safe_stem = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in source_stem)
    safe_stem = safe_stem.strip("_") or "wordbook"
    candidate = wordbooks_dir / f"imported_{safe_stem}.json"
    index = 2
    while candidate.exists():
        candidate = wordbooks_dir / f"imported_{safe_stem}_{index}.json"
        index += 1
    return candidate


def _first_import_text(raw_entry: dict[object, object], *names: str) -> str:
    for name in names:
        value = raw_entry.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int | float) and not isinstance(value, bool):
            return str(value)
    return ""


def _first_import_lines(raw_entry: dict[object, object], *names: str) -> list[str]:
    for name in names:
        value = raw_entry.get(name)
        lines = _coerce_import_lines(value)
        if lines:
            return lines
    return []


def _coerce_import_lines(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.replace("|", ";").replace("/", ";").replace("；", ";").split(";")
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, Iterable):
        lines: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                lines.append(item.strip())
            elif isinstance(item, dict):
                text = _first_import_text(
                    _flatten_import_entry(item),
                    "definition",
                    "definitionCn",
                    "translation",
                    "meaning",
                    "trans",
                    "tran",
                    "tranCn",
                    "chinese",
                    "cn",
                    "释义",
                )
                if text:
                    lines.extend(_coerce_import_lines(text))
        return lines
    return []


def _flatten_import_entry(raw_entry: dict[object, object]) -> dict[object, object]:
    flattened: dict[object, object] = dict(raw_entry)
    for value in raw_entry.values():
        if isinstance(value, dict):
            flattened.update(_flatten_import_entry(value))
    return flattened


def _is_mastered(state: LearningState, word: str) -> bool:
    progress = _progress_for_word(state, word)
    return progress.mastered if progress is not None else False


def _is_due_for_review(state: LearningState, word: str, now: datetime) -> bool:
    progress = _progress_for_word(state, word)
    return is_due(progress, now) if progress is not None else False


def _progress_for_word(state: LearningState, word: str):
    progress = state.progress.get(word)
    if progress is None:
        progress = state.progress.get(word.casefold())
    return progress
