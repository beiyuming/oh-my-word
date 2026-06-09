from __future__ import annotations

import json
from pathlib import Path


def test_enriched_kaoyan_wordbook_has_pronunciation_and_examples() -> None:
    path = Path("data/wordbooks/zz_kaoyan_enriched.json")

    entries = json.loads(path.read_text(encoding="utf-8"))

    assert isinstance(entries, list)
    assert len(entries) == 5528
    assert _missing_ipa_count(entries) == 0
    assert _placeholder_example_count(entries) == 0


def test_default_wordbooks_keep_only_enriched_kaoyan_json() -> None:
    json_files = sorted(path.name for path in Path("data/wordbooks").glob("*.json"))

    assert json_files == ["zz_kaoyan_enriched.json"]


def _missing_ipa_count(entries: list[object]) -> int:
    return sum(
        1
        for entry in entries
        if isinstance(entry, dict)
        and (not entry.get("ipa") or entry.get("ipa") == "/.../")
    )


def _placeholder_example_count(entries: list[object]) -> int:
    return sum(
        1
        for entry in entries
        if isinstance(entry, dict)
        and (
            not entry.get("example_sentence")
            or entry.get("example_sentence") == entry.get("word")
            or not entry.get("example_translation")
            or entry.get("example_translation") == "暂无例句翻译。"
        )
    )
