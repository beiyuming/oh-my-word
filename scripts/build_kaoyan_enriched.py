from __future__ import annotations

import json
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
FILTER_PATH = Path(".tmp-endict-kaoyan.json")
FILTER_URL = "https://raw.githubusercontent.com/ismartcoding/endict/main/vocabulary/kaoyan.json"
BASELINE_PATH = Path("data/wordbooks/kaoyan_full.json")


def main() -> int:
    allowed_words = _load_allowed_words()
    merged: dict[str, dict[str, Any]] = {}
    for source_path, source_url in SOURCE_FILES:
        payload = _load_json(source_path, source_url)
        if not isinstance(payload, list):
            raise ValueError(f"{source_path} root is not a list")
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            local = _entry_to_local(raw)
            if local is not None:
                if allowed_words and local["word"].casefold() not in allowed_words:
                    continue
                merged[local["word"].casefold()] = local

    entries = sorted(merged.values(), key=lambda item: item["word"].casefold())
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


def _load_allowed_words() -> set[str]:
    allowed_words = _load_word_list(FILTER_PATH, FILTER_URL)
    baseline_words = _load_wordbook_words(BASELINE_PATH)
    if allowed_words and baseline_words:
        return allowed_words & baseline_words
    return allowed_words or baseline_words


def _load_word_list(path: Path, url: str | None = None) -> set[str]:
    if not path.exists() and url is None:
        return set()
    payload = _load_json(path, url)
    if not isinstance(payload, list):
        raise ValueError(f"{path} root is not a list")
    return {
        item.strip().casefold()
        for item in payload
        if isinstance(item, str) and item.strip()
    }


def _load_wordbook_words(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} root is not a list")
    words: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        word = _clean_text(item.get("word"))
        if word:
            words.add(word.casefold())
    return words


def _load_json(path: Path, url: str | None = None) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if url is None:
        raise FileNotFoundError(path)
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


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


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def _normalize_ipa(value: str) -> str:
    normalized = _clean_text(value)
    if not normalized:
        return ""
    if normalized.startswith("/") and normalized.endswith("/"):
        return normalized
    return f"/{normalized}/"


if __name__ == "__main__":
    raise SystemExit(main())
