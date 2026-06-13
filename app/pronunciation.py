from __future__ import annotations

from typing import Any

from .models import PronunciationContentMode


def pronunciation_text(entry: Any, mode: PronunciationContentMode) -> str:
    term = _first_text(entry, "term", "word", "text")
    example_sentence = _first_text(entry, "example_sentence", "sentence", "example")
    has_distinct_example = bool(example_sentence) and example_sentence.casefold() != term.casefold()

    if mode is PronunciationContentMode.WORD:
        return term or example_sentence
    if mode is PronunciationContentMode.EXAMPLE:
        return example_sentence if has_distinct_example else term
    if term and has_distinct_example:
        return f"{term}.\n\n{example_sentence}"
    return term or example_sentence


def _first_text(source: Any, *names: str) -> str:
    for name in names:
        value = getattr(source, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
