from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path


class DisplayMode(str, Enum):
    CARD = "card"
    BARRAGE = "barrage"


class OverlayPosition(str, Enum):
    NEAR_MOUSE = "near_mouse"
    BOTTOM_RIGHT = "bottom_right"
    TOP_CENTER = "top_center"
    CENTER = "center"
    RANDOM = "random"


class Accent(str, Enum):
    UK = "uk"
    US = "us"


class TtsProvider(str, Enum):
    SYSTEM_QT = "system_qt"
    VOXCPM_LOCAL = "voxcpm_local"


class PronunciationContentMode(str, Enum):
    WORD = "word"
    EXAMPLE = "example"
    WORD_AND_EXAMPLE = "word_and_example"


class TtsInitializationState(str, Enum):
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"
    UNAVAILABLE = "unavailable"


DEFAULT_MIN_DELAY_MINUTES = 8
DEFAULT_MAX_DELAY_MINUTES = 20
DEFAULT_BUSY_STOP_THRESHOLD_SECONDS = 8
DEFAULT_ACTIVITY_THRESHOLD_PER_MINUTE = 90
DEFAULT_ACTIVITY_SLOWDOWN_WEIGHT = 100
DEFAULT_POPUP_DURATION_SECONDS = 6
DEFAULT_SNOOZE_MINUTES = 30
DEFAULT_RECENT_WORDS_LIMIT = 20
DEFAULT_VOXCPM_ENDPOINT = "http://127.0.0.1:8808"
DEFAULT_VOXCPM_TIMEOUT_SECONDS = 15
DEFAULT_VOXCPM_INSTALL_ROOT = str(
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    / "OhMyWord"
    / "voxcpm"
)
DEFAULT_VOXCPM_MODEL_CACHE_ROOT = str(Path(DEFAULT_VOXCPM_INSTALL_ROOT) / "models")

DEFAULT_PRONOUNCE_HOTKEY = "Ctrl+Alt+1"
DEFAULT_TOGGLE_DETAIL_HOTKEY = "Ctrl+Alt+2"
DEFAULT_TRIGGER_NOW_HOTKEY = "Ctrl+Alt+3"
DEFAULT_MARK_MASTERED_HOTKEY = "Ctrl+Alt+4"
DEFAULT_KNOWN_HOTKEY = "Ctrl+Alt+5"
DEFAULT_UNKNOWN_HOTKEY = "Ctrl+Alt+6"
DEFAULT_DISMISS_HOTKEY = "Ctrl+Alt+7"


@dataclass(slots=True)
class AppSettings:
    enabled: bool = True
    display_mode: DisplayMode = DisplayMode.CARD
    card_position: OverlayPosition = OverlayPosition.BOTTOM_RIGHT
    barrage_position: OverlayPosition = OverlayPosition.TOP_CENTER
    min_delay_minutes: int = DEFAULT_MIN_DELAY_MINUTES
    max_delay_minutes: int = DEFAULT_MAX_DELAY_MINUTES
    busy_stop_threshold_seconds: int = DEFAULT_BUSY_STOP_THRESHOLD_SECONDS
    activity_threshold_per_minute: int = DEFAULT_ACTIVITY_THRESHOLD_PER_MINUTE
    activity_slowdown_weight: int = DEFAULT_ACTIVITY_SLOWDOWN_WEIGHT
    popup_duration_seconds: int = DEFAULT_POPUP_DURATION_SECONDS
    snooze_minutes: int = DEFAULT_SNOOZE_MINUTES
    mute_pronunciation: bool = False
    pronunciation_content_mode: PronunciationContentMode = PronunciationContentMode.WORD_AND_EXAMPLE
    accent: Accent = Accent.US
    tts_provider: TtsProvider = TtsProvider.SYSTEM_QT
    voxcpm_endpoint: str = DEFAULT_VOXCPM_ENDPOINT
    voxcpm_timeout_seconds: int = DEFAULT_VOXCPM_TIMEOUT_SECONDS
    voxcpm_install_root: str = DEFAULT_VOXCPM_INSTALL_ROOT
    voxcpm_model_cache_root: str = DEFAULT_VOXCPM_MODEL_CACHE_ROOT
    voxcpm_use_model_mirror: bool = True
    voxcpm_auto_start: bool = False
    pronounce_hotkey: str = DEFAULT_PRONOUNCE_HOTKEY
    toggle_detail_hotkey: str = DEFAULT_TOGGLE_DETAIL_HOTKEY
    trigger_now_hotkey: str = DEFAULT_TRIGGER_NOW_HOTKEY
    mark_mastered_hotkey: str = DEFAULT_MARK_MASTERED_HOTKEY
    known_hotkey: str = DEFAULT_KNOWN_HOTKEY
    unknown_hotkey: str = DEFAULT_UNKNOWN_HOTKEY
    dismiss_hotkey: str = DEFAULT_DISMISS_HOTKEY


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
    last_reviewed_at: str | None = None
    due_at: str | None = None
    review_count: int = 0
    known_count: int = 0
    unknown_count: int = 0
    stability: float = 0.0
    difficulty: float = 5.0
    last_rating: str | None = None
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
