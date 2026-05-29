from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DisplayMode(str, Enum):
    CARD = "card"
    BARRAGE = "barrage"


class OverlayPosition(str, Enum):
    NEAR_MOUSE = "near_mouse"
    BOTTOM_RIGHT = "bottom_right"
    TOP_CENTER = "top_center"
    CENTER = "center"


class Accent(str, Enum):
    UK = "uk"
    US = "us"


DEFAULT_MIN_DELAY_MINUTES = 8
DEFAULT_MAX_DELAY_MINUTES = 20
DEFAULT_BUSY_STOP_THRESHOLD_SECONDS = 8
DEFAULT_POPUP_DURATION_SECONDS = 6
DEFAULT_RECENT_WORDS_LIMIT = 20

DEFAULT_PRONOUNCE_HOTKEY = "Alt+1"
DEFAULT_TOGGLE_DETAIL_HOTKEY = "Alt+2"
DEFAULT_TRIGGER_NOW_HOTKEY = "Alt+3"
DEFAULT_MARK_MASTERED_HOTKEY = "Alt+4"


@dataclass(slots=True)
class AppSettings:
    enabled: bool = True
    display_mode: DisplayMode = DisplayMode.CARD
    card_position: OverlayPosition = OverlayPosition.BOTTOM_RIGHT
    barrage_position: OverlayPosition = OverlayPosition.TOP_CENTER
    min_delay_minutes: int = DEFAULT_MIN_DELAY_MINUTES
    max_delay_minutes: int = DEFAULT_MAX_DELAY_MINUTES
    busy_stop_threshold_seconds: int = DEFAULT_BUSY_STOP_THRESHOLD_SECONDS
    popup_duration_seconds: int = DEFAULT_POPUP_DURATION_SECONDS
    mute_pronunciation: bool = False
    accent: Accent = Accent.US
    pronounce_hotkey: str = DEFAULT_PRONOUNCE_HOTKEY
    toggle_detail_hotkey: str = DEFAULT_TOGGLE_DETAIL_HOTKEY
    trigger_now_hotkey: str = DEFAULT_TRIGGER_NOW_HOTKEY
    mark_mastered_hotkey: str = DEFAULT_MARK_MASTERED_HOTKEY


@dataclass(slots=True)
class WordEntry:
    word: str
    ipa: str
    part_of_speech: str
    definitions: list[str]
    example_sentence: str
    example_translation: str


@dataclass(slots=True)
class WordProgress:
    show_count: int = 0
    last_shown_at: str | None = None
    last_pronounced_at: str | None = None
    last_expanded_at: str | None = None
    mastered: bool = False


@dataclass(slots=True)
class LearningState:
    recent_words: list[str] = field(default_factory=list)
    progress: dict[str, WordProgress] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class WordSelectionResult:
    word: WordEntry | None
    should_pause: bool
    notice_key: str | None = None
    used_recent_fallback: bool = False


@dataclass(slots=True, frozen=True)
class WordbookIssue:
    source: str
    message: str
