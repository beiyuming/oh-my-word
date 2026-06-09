from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol
from urllib.parse import urlparse

from .models import (
    Accent,
    AppSettings,
    DEFAULT_ACTIVITY_THRESHOLD_PER_MINUTE,
    DEFAULT_ACTIVITY_SLOWDOWN_WEIGHT,
    DEFAULT_BUSY_STOP_THRESHOLD_SECONDS,
    DEFAULT_DISMISS_HOTKEY,
    DEFAULT_KNOWN_HOTKEY,
    DEFAULT_MARK_MASTERED_HOTKEY,
    DEFAULT_MAX_DELAY_MINUTES,
    DEFAULT_MIN_DELAY_MINUTES,
    DEFAULT_UNKNOWN_HOTKEY,
    DEFAULT_POPUP_DURATION_SECONDS,
    DEFAULT_PRONOUNCE_HOTKEY,
    DEFAULT_SNOOZE_MINUTES,
    DEFAULT_TOGGLE_DETAIL_HOTKEY,
    DEFAULT_TRIGGER_NOW_HOTKEY,
    DEFAULT_VOXCPM_ENDPOINT,
    DEFAULT_VOXCPM_TIMEOUT_SECONDS,
    DisplayMode,
    LearningState,
    OverlayPosition,
    TtsProvider,
    WordProgress,
)


class AppPathsLike(Protocol):
    storage_dir: Path
    settings_path: Path
    learning_state_path: Path
    log_path: Path


_MODULE_LOGGER = logging.getLogger("oh_my_word.settings")


def ensure_storage_layout(paths: AppPathsLike) -> None:
    paths.storage_dir.mkdir(parents=True, exist_ok=True)


def setup_app_logger(paths: AppPathsLike) -> logging.Logger:
    logger = logging.getLogger("oh_my_word")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    ensure_storage_layout(paths)
    log_path = paths.log_path.resolve()

    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_path:
            return logger

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1024 * 1024,
        backupCount=1,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    for existing in list(logger.handlers):
        logger.removeHandler(existing)
        try:
            existing.close()
        except Exception:
            pass

    logger.addHandler(handler)
    return logger


class SettingsStore:
    def __init__(self, paths: AppPathsLike, logger: logging.Logger | None = None) -> None:
        self._paths = paths
        self._logger = logger or _MODULE_LOGGER

    def load(self) -> AppSettings:
        payload = _read_json_object(self._paths.settings_path, self._logger)
        return normalize_settings(payload)

    def save(self, settings: AppSettings) -> AppSettings:
        normalized = normalize_settings(asdict(settings))
        _write_json_file(self._paths.settings_path, settings_to_dict(normalized), self._logger)
        return normalized


class LearningStateStore:
    def __init__(self, paths: AppPathsLike, logger: logging.Logger | None = None) -> None:
        self._paths = paths
        self._logger = logger or _MODULE_LOGGER

    def load(self) -> LearningState:
        payload = _read_json_object(self._paths.learning_state_path, self._logger)
        return normalize_learning_state(payload)

    def save(self, state: LearningState) -> LearningState:
        normalized = normalize_learning_state(asdict(state))
        _write_json_file(
            self._paths.learning_state_path,
            learning_state_to_dict(normalized),
            self._logger,
        )
        return normalized


def normalize_settings(payload: Any) -> AppSettings:
    data = payload if isinstance(payload, dict) else {}
    defaults = AppSettings()

    min_delay = _normalize_positive_int(data.get("min_delay_minutes"), DEFAULT_MIN_DELAY_MINUTES)
    max_delay = _normalize_positive_int(data.get("max_delay_minutes"), DEFAULT_MAX_DELAY_MINUTES)
    max_delay = max(min_delay, max_delay)

    return AppSettings(
        enabled=_normalize_bool(data.get("enabled"), defaults.enabled),
        display_mode=_normalize_enum(data.get("display_mode"), DisplayMode, defaults.display_mode),
        card_position=_normalize_enum(
            data.get("card_position"),
            OverlayPosition,
            defaults.card_position,
        ),
        barrage_position=_normalize_enum(
            data.get("barrage_position"),
            OverlayPosition,
            defaults.barrage_position,
        ),
        min_delay_minutes=min_delay,
        max_delay_minutes=max_delay,
        busy_stop_threshold_seconds=_normalize_positive_int(
            data.get("busy_stop_threshold_seconds"),
            DEFAULT_BUSY_STOP_THRESHOLD_SECONDS,
        ),
        activity_threshold_per_minute=_normalize_positive_int(
            data.get("activity_threshold_per_minute"),
            DEFAULT_ACTIVITY_THRESHOLD_PER_MINUTE,
        ),
        activity_slowdown_weight=_normalize_non_negative_int(
            data.get("activity_slowdown_weight"),
            DEFAULT_ACTIVITY_SLOWDOWN_WEIGHT,
        ),
        popup_duration_seconds=_normalize_positive_int(
            data.get("popup_duration_seconds"),
            DEFAULT_POPUP_DURATION_SECONDS,
        ),
        snooze_minutes=_normalize_positive_int(
            data.get("snooze_minutes"),
            DEFAULT_SNOOZE_MINUTES,
        ),
        mute_pronunciation=_normalize_bool(data.get("mute_pronunciation"), defaults.mute_pronunciation),
        accent=_normalize_enum(data.get("accent"), Accent, defaults.accent),
        tts_provider=_normalize_enum(data.get("tts_provider"), TtsProvider, defaults.tts_provider),
        voxcpm_endpoint=_normalize_local_http_endpoint(
            data.get("voxcpm_endpoint"),
            defaults.voxcpm_endpoint,
        ),
        voxcpm_timeout_seconds=_normalize_timeout_seconds(
            data.get("voxcpm_timeout_seconds"),
            DEFAULT_VOXCPM_TIMEOUT_SECONDS,
        ),
        pronounce_hotkey=_normalize_hotkey(
            data.get("pronounce_hotkey"),
            DEFAULT_PRONOUNCE_HOTKEY,
        ),
        toggle_detail_hotkey=_normalize_hotkey(
            data.get("toggle_detail_hotkey"),
            DEFAULT_TOGGLE_DETAIL_HOTKEY,
        ),
        trigger_now_hotkey=_normalize_hotkey(
            data.get("trigger_now_hotkey"),
            DEFAULT_TRIGGER_NOW_HOTKEY,
        ),
        mark_mastered_hotkey=_normalize_hotkey(
            data.get("mark_mastered_hotkey"),
            DEFAULT_MARK_MASTERED_HOTKEY,
        ),
        known_hotkey=_normalize_hotkey(
            data.get("known_hotkey"),
            DEFAULT_KNOWN_HOTKEY,
        ),
        unknown_hotkey=_normalize_hotkey(
            data.get("unknown_hotkey"),
            DEFAULT_UNKNOWN_HOTKEY,
        ),
        dismiss_hotkey=_normalize_hotkey(
            data.get("dismiss_hotkey"),
            DEFAULT_DISMISS_HOTKEY,
        ),
    )


def normalize_learning_state(payload: Any) -> LearningState:
    data = payload if isinstance(payload, dict) else {}
    recent_words = [
        item.strip()
        for item in data.get("recent_words", [])
        if isinstance(item, str) and item.strip()
    ] if isinstance(data.get("recent_words"), list) else []

    progress_payload = data.get("progress") if isinstance(data.get("progress"), dict) else {}
    progress: dict[str, WordProgress] = {}
    for raw_key, raw_value in progress_payload.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            continue
        key = raw_key.strip()
        payload_dict = raw_value if isinstance(raw_value, dict) else {}
        progress[key] = WordProgress(
            show_count=_normalize_non_negative_int(payload_dict.get("show_count"), 0),
            last_shown_at=_normalize_optional_text(payload_dict.get("last_shown_at")),
            last_pronounced_at=_normalize_optional_text(payload_dict.get("last_pronounced_at")),
            last_expanded_at=_normalize_optional_text(payload_dict.get("last_expanded_at")),
            last_reviewed_at=_normalize_optional_text(payload_dict.get("last_reviewed_at")),
            due_at=_normalize_optional_text(payload_dict.get("due_at")),
            review_count=_normalize_non_negative_int(payload_dict.get("review_count"), 0),
            known_count=_normalize_non_negative_int(payload_dict.get("known_count"), 0),
            unknown_count=_normalize_non_negative_int(payload_dict.get("unknown_count"), 0),
            stability=_normalize_non_negative_float(payload_dict.get("stability"), 0.0),
            difficulty=_normalize_positive_float(payload_dict.get("difficulty"), 5.0),
            last_rating=_normalize_optional_text(payload_dict.get("last_rating")),
            mastered=_normalize_bool(payload_dict.get("mastered"), False),
        )

    return LearningState(recent_words=recent_words, progress=progress)


def settings_to_dict(settings: AppSettings) -> dict[str, Any]:
    return {
        "enabled": settings.enabled,
        "display_mode": settings.display_mode.value,
        "card_position": settings.card_position.value,
        "barrage_position": settings.barrage_position.value,
        "min_delay_minutes": settings.min_delay_minutes,
        "max_delay_minutes": settings.max_delay_minutes,
        "busy_stop_threshold_seconds": settings.busy_stop_threshold_seconds,
        "activity_threshold_per_minute": settings.activity_threshold_per_minute,
        "activity_slowdown_weight": settings.activity_slowdown_weight,
        "popup_duration_seconds": settings.popup_duration_seconds,
        "snooze_minutes": settings.snooze_minutes,
        "mute_pronunciation": settings.mute_pronunciation,
        "accent": settings.accent.value,
        "tts_provider": settings.tts_provider.value,
        "voxcpm_endpoint": settings.voxcpm_endpoint,
        "voxcpm_timeout_seconds": settings.voxcpm_timeout_seconds,
        "pronounce_hotkey": settings.pronounce_hotkey,
        "toggle_detail_hotkey": settings.toggle_detail_hotkey,
        "trigger_now_hotkey": settings.trigger_now_hotkey,
        "mark_mastered_hotkey": settings.mark_mastered_hotkey,
        "known_hotkey": settings.known_hotkey,
        "unknown_hotkey": settings.unknown_hotkey,
        "dismiss_hotkey": settings.dismiss_hotkey,
    }


def learning_state_to_dict(state: LearningState) -> dict[str, Any]:
    return {
        "recent_words": list(state.recent_words),
        "progress": {
            key: {
                "show_count": progress.show_count,
                "last_shown_at": progress.last_shown_at,
                "last_pronounced_at": progress.last_pronounced_at,
                "last_expanded_at": progress.last_expanded_at,
                "last_reviewed_at": progress.last_reviewed_at,
                "due_at": progress.due_at,
                "review_count": progress.review_count,
                "known_count": progress.known_count,
                "unknown_count": progress.unknown_count,
                "stability": progress.stability,
                "difficulty": progress.difficulty,
                "last_rating": progress.last_rating,
                "mastered": progress.mastered,
            }
            for key, progress in state.progress.items()
        },
    }


def _read_json_object(path: Path, logger: logging.Logger) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return {}

    if isinstance(payload, dict):
        return payload

    logger.warning("Ignoring non-object JSON payload in %s", path)
    return {}


def _write_json_file(path: Path, payload: dict[str, Any], logger: logging.Logger) -> None:
    temp_path: Path | None = None
    try:
        ensure_storage_layout(_SimplePaths(path.parent, path))
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    except OSError as exc:
        logger.warning("Failed to write %s: %s", path, exc)
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


class _SimplePaths:
    def __init__(self, storage_dir: Path, file_path: Path) -> None:
        self.storage_dir = storage_dir
        self.settings_path = file_path
        self.learning_state_path = file_path
        self.log_path = file_path


def _normalize_enum(value: Any, enum_type: Any, default: Any) -> Any:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for member in enum_type:
            if member.value == normalized:
                return member
    return default


def _normalize_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _normalize_positive_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else default


def _normalize_local_http_endpoint(value: Any, default: str = DEFAULT_VOXCPM_ENDPOINT) -> str:
    text = _normalize_optional_text(value) or default
    parsed = urlparse(text)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "http":
        return default
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        return default
    if parsed.port is None:
        return default
    return text.rstrip("/")


def _normalize_timeout_seconds(value: Any, default: int) -> int:
    timeout = _normalize_positive_int(value, default)
    return min(max(timeout, 1), 120)


def _normalize_non_negative_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default


def _normalize_non_negative_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float) and value >= 0:
        return float(value)
    return default


def _normalize_positive_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float) and value > 0:
        return float(value)
    return default


def _normalize_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_hotkey(value: Any, default: str) -> str:
    normalized = _normalize_optional_text(value)
    return normalized if normalized is not None else default
