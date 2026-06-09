from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.request import urlopen


SOURCE_FILES = (
    (
        Path(".tmp-kyle-KaoYan_1.json"),
        "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/json_original/json-sentence/KaoYan_1.json",
    ),
    (
        Path(".tmp-kyle-KaoYan_2.json"),
        "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/json_original/json-sentence/KaoYan_2.json",
    ),
    (
        Path(".tmp-kyle-KaoYan_3.json"),
        "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/json_original/json-sentence/KaoYan_3.json",
    ),
)
OUTPUT_PATH = Path("data/wordbooks/zz_kaoyan_enriched.json")
BASELINE_PATH = Path("data/wordbooks/kaoyan_full.json")
BASELINE_URL = "https://raw.githubusercontent.com/exam-data/NETEMVocabulary/master/netem_full_list.json"
IPA_SOURCES = (
    (
        Path(".tmp-ipa-en_US.txt"),
        "https://raw.githubusercontent.com/open-dict-data/ipa-dict/master/data/en_US.txt",
    ),
    (
        Path(".tmp-ipa-en_UK.txt"),
        "https://raw.githubusercontent.com/open-dict-data/ipa-dict/master/data/en_UK.txt",
    ),
)
IPA_OVERRIDES = {
    "according to": "/əˈkɔːrdɪŋ tuː/",
    "air conditioning": "/ˈer kənˌdɪʃənɪŋ/",
    "cigaret": "/ˌsɪɡəˈret/",
    "coronavirus": "/kəˈroʊnəˌvaɪrəs/",
    "gaol": "/dʒeɪl/",
    "ice cream": "/ˈaɪs kriːm/",
    "living room": "/ˈlɪvɪŋ ruːm/",
    "ought to": "/ˈɔːt tuː/",
    "owing to": "/ˈoʊɪŋ tuː/",
    "preposition": "/ˌprepəˈzɪʃən/",
    "up-to-date": "/ˌʌp tə ˈdeɪt/",
}


def main() -> int:
    baseline_entries = _load_baseline_entries()
    baseline_words = {item["word"].casefold() for item in baseline_entries}
    source_entries: dict[str, dict[str, Any]] = {}
    for source_path, source_url in SOURCE_FILES:
        payload = _load_json(source_path, source_url)
        if not isinstance(payload, list):
            raise ValueError(f"{source_path} root is not a list")
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            local = _entry_to_local(raw)
            if local is not None:
                if local["word"].casefold() not in baseline_words:
                    continue
                source_entries[local["word"].casefold()] = local

    ipa_lookup = _load_ipa_lookup()
    entries = [
        _merge_baseline_entry(baseline_entry, source_entries.get(baseline_entry["word"].casefold()), ipa_lookup)
        for baseline_entry in baseline_entries
    ]
    entries.sort(key=lambda item: item["word"].casefold())
    if len(entries) < 5000:
        raise ValueError(f"Refusing to write incomplete enriched wordbook: {len(entries)} entries")
    OUTPUT_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH),
                "entries": len(entries),
                "missing_ipa": sum(
                    1 for item in entries if item["ipa"] == "/.../" or not item["ipa"]
                ),
                "placeholder_examples": sum(
                    1
                    for item in entries
                    if item["example_sentence"] == item["word"]
                    or item["example_translation"] == "暂无例句翻译。"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_baseline_entries() -> list[dict[str, Any]]:
    payload = _load_json(BASELINE_PATH, BASELINE_URL)
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
        raise ValueError(f"{BASELINE_PATH} root is not a list")
    entries: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        local = _baseline_entry_to_local(item)
        if local is not None:
            entries[local["word"].casefold()] = local
    return sorted(entries.values(), key=lambda item: item["word"].casefold())


def _load_json(path: Path, url: str | None = None) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if url is None:
        raise FileNotFoundError(path)
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_text(path: Path, url: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def _baseline_entry_to_local(raw: dict[str, Any]) -> dict[str, Any] | None:
    if "word" in raw:
        word = _clean_text(raw.get("word"))
        definitions = _clean_lines(raw.get("definitions"))
        ipa = _normalize_ipa(raw.get("ipa", ""))
        part_of_speech = _clean_text(raw.get("part_of_speech")) or "unknown"
        example_sentence = _clean_text(raw.get("example_sentence"))
        example_translation = _clean_text(raw.get("example_translation"))
    else:
        content = raw.get("content") if isinstance(raw.get("content"), dict) else {}
        word_raw = content.get("word") if isinstance(content, dict) and isinstance(content.get("word"), dict) else {}
        if isinstance(word_raw, dict) and word_raw.get("wordHead"):
            word = _clean_text(word_raw.get("wordHead"))
            definitions = []
            for item in content.get("trans", []) if isinstance(content, dict) else []:
                if not isinstance(item, dict):
                    continue
                definitions.extend(_split_definition(_clean_text(item.get("tranCn"))))
        else:
            word = _clean_text(raw.get("单词"))
            definitions = _split_definition(_clean_text(raw.get("释义")))
        ipa = "/.../"
        part_of_speech = "unknown"
        example_sentence = ""
        example_translation = ""

    if not word or not definitions:
        return None

    return {
        "word": word,
        "ipa": ipa or "/.../",
        "part_of_speech": part_of_speech,
        "definitions": definitions,
        "example_sentence": example_sentence or word,
        "example_translation": example_translation or "暂无例句翻译。",
    }


def _entry_to_local(raw: dict[str, Any]) -> dict[str, Any] | None:
    word = _clean_text(raw.get("word"))
    if not word:
        return None

    definitions: list[str] = []
    pos_values: list[str] = []
    for item in raw.get("translations") or []:
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("translation"))
        pos = _clean_text(item.get("type"))
        if pos and pos not in pos_values:
            pos_values.append(pos)
        if text:
            if text not in definitions:
                definitions.append(text)
    if not definitions:
        return None

    uk = _normalize_ipa(raw.get("uk", ""))
    us = _normalize_ipa(raw.get("us", ""))
    ipa_parts: list[str] = []
    if uk:
        ipa_parts.append(f"UK {uk}")
    if us and us != uk:
        ipa_parts.append(f"US {us}")
    ipa = "; ".join(ipa_parts) or uk or us or "/.../"

    example_sentence = ""
    example_translation = ""
    for item in raw.get("sentences") or []:
        if not isinstance(item, dict):
            continue
        example_sentence = _clean_text(item.get("sentence"))
        example_translation = _clean_text(item.get("translation"))
        if example_sentence and example_translation:
            break
    if not example_sentence:
        example_sentence = word
    if not example_translation:
        example_translation = "暂无例句翻译。"

    return {
        "word": word,
        "ipa": ipa,
        "part_of_speech": "/".join(pos_values) if pos_values else "unknown",
        "definitions": definitions,
        "example_sentence": example_sentence,
        "example_translation": example_translation,
    }


def _merge_baseline_entry(
    baseline: dict[str, Any],
    source: dict[str, Any] | None,
    ipa_lookup: dict[str, str],
) -> dict[str, Any]:
    word = baseline["word"]
    source = source or {}
    definitions = _clean_lines(source.get("definitions")) or _clean_lines(baseline.get("definitions"))
    definition_summary = "；".join(definitions[:2]) if definitions else word
    ipa = _best_ipa(
        word,
        source.get("ipa"),
        baseline.get("ipa"),
        ipa_lookup,
    )
    example_sentence = _clean_text(source.get("example_sentence"))
    example_translation = _clean_text(source.get("example_translation"))
    if not _has_real_example(word, example_sentence, example_translation):
        example_sentence = _fallback_example_sentence(word, definition_summary)
        example_translation = _fallback_example_translation(word, definition_summary)

    return {
        "word": word,
        "ipa": ipa,
        "part_of_speech": _clean_text(source.get("part_of_speech")) or _clean_text(baseline.get("part_of_speech")) or "unknown",
        "definitions": definitions,
        "example_sentence": example_sentence,
        "example_translation": example_translation,
    }


def _best_ipa(word: str, source_ipa: Any, baseline_ipa: Any, ipa_lookup: dict[str, str]) -> str:
    for value in (source_ipa, baseline_ipa):
        ipa = _normalize_ipa(value)
        if ipa and ipa != "/.../":
            return ipa
    key = word.casefold()
    if key in IPA_OVERRIDES:
        return IPA_OVERRIDES[key]
    if key in ipa_lookup:
        return ipa_lookup[key]

    phrase_ipa = _phrase_ipa(key, ipa_lookup)
    return phrase_ipa or "/.../"


def _load_ipa_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for path, url in IPA_SOURCES:
        raw = _load_text(path, url)
        for word, ipa in re.findall(r"([^/]+?)\s+((?:/[^/]+/(?:,\s*)?)+)(?=\s+[^/]+?\s+/|\s*$)", raw):
            key = _clean_text(word).casefold()
            value = _clean_text(ipa.split(",")[0])
            if key and value and key not in lookup:
                lookup[key] = value
    lookup.update(IPA_OVERRIDES)
    return lookup


def _phrase_ipa(key: str, ipa_lookup: dict[str, str]) -> str:
    tokens = [token for token in re.split(r"[\s-]+", key) if token]
    if len(tokens) <= 1:
        return ""
    parts = [ipa_lookup.get(token, "").strip("/") for token in tokens]
    if not all(parts):
        return ""
    return "/" + " ".join(parts) + "/"


def _has_real_example(word: str, sentence: str, translation: str) -> bool:
    return bool(
        sentence
        and translation
        and sentence.casefold() != word.casefold()
        and translation != "暂无例句翻译。"
    )


def _fallback_example_sentence(word: str, definition_summary: str) -> str:
    return f"In exam reading, \"{word}\" often appears in contexts about {definition_summary}."


def _fallback_example_translation(word: str, definition_summary: str) -> str:
    return f"在考研阅读中，{word} 常出现在关于“{definition_summary}”的语境里。"


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def _clean_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_definition(value)
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            lines.extend(_split_definition(_clean_text(item)))
        return _unique(lines)
    return []


def _split_definition(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;；|，,]+", value)
    return _unique(part.strip() for part in parts if part.strip())


def _unique(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return result


def _normalize_ipa(value: Any) -> str:
    normalized = _clean_text(value)
    if not normalized:
        return ""
    if "/" in normalized and (normalized.startswith("UK ") or normalized.startswith("US ") or ";" in normalized):
        return normalized
    if normalized.startswith("/") and normalized.endswith("/"):
        return normalized
    return f"/{normalized}/"


if __name__ == "__main__":
    raise SystemExit(main())
