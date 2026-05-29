from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from .models import (
    Accent,
    AppSettings,
    DEFAULT_BUSY_STOP_THRESHOLD_SECONDS,
    DEFAULT_MARK_MASTERED_HOTKEY,
    DEFAULT_MAX_DELAY_MINUTES,
    DEFAULT_MIN_DELAY_MINUTES,
    DEFAULT_POPUP_DURATION_SECONDS,
    DEFAULT_PRONOUNCE_HOTKEY,
    DEFAULT_TOGGLE_DETAIL_HOTKEY,
    DEFAULT_TRIGGER_NOW_HOTKEY,
    DisplayMode,
    LearningState,
    OverlayPosition,
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
        popup_duration_seconds=_normalize_positive_int(
            data.get("popup_duration_seconds"),
            DEFAULT_POPUP_DURATION_SECONDS,
        ),
        mute_pronunciation=_normalize_bool(data.get("mute_pronunciation"), defaults.mute_pronunciation),
        accent=_normalize_enum(data.get("accent"), Accent, defaults.accent),
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
        "popup_duration_seconds": settings.popup_duration_seconds,
        "mute_pronunciation": settings.mute_pronunciation,
        "accent": settings.accent.value,
        "pronounce_hotkey": settings.pronounce_hotkey,
        "toggle_detail_hotkey": settings.toggle_detail_hotkey,
        "trigger_now_hotkey": settings.trigger_now_hotkey,
        "mark_mastered_hotkey": settings.mark_mastered_hotkey,
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


def _normalize_non_negative_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default


def _normalize_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_hotkey(value: Any, default: str) -> str:
    normalized = _normalize_optional_text(value)
    return normalized if normalized is not None else default
