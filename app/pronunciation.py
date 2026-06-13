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


def voxcpm_pronunciation_text(
    entry: Any,
    mode: PronunciationContentMode,
    *,
    voice_prompt: str = "",
) -> str:
    term = _first_text(entry, "term", "word", "text")
    example_sentence = _first_text(entry, "example_sentence", "sentence", "example")
    has_distinct_example = bool(example_sentence) and example_sentence.casefold() != term.casefold()

    if mode is PronunciationContentMode.EXAMPLE and has_distinct_example:
        return _with_voxcpm_voice_prompt(example_sentence, voice_prompt)
    if mode is PronunciationContentMode.WORD_AND_EXAMPLE and term and has_distinct_example:
        return _with_voxcpm_voice_prompt(f"{_quoted_word_sentence(term)} {example_sentence}", voice_prompt)
    if term:
        return _with_voxcpm_voice_prompt(_quoted_word_sentence(term), voice_prompt)
    return _with_voxcpm_voice_prompt(example_sentence, voice_prompt)


def _first_text(source: Any, *names: str) -> str:
    for name in names:
        value = getattr(source, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _quoted_word_sentence(term: str) -> str:
    escaped = term.replace('"', '\\"')
    return f'"{escaped}".'


def _with_voxcpm_voice_prompt(text: str, voice_prompt: str) -> str:
    message = text.strip()
    prompt = " ".join(voice_prompt.split()).strip().strip("()").strip()
    if not message or not prompt:
        return message
    return f"({prompt}){message}"
