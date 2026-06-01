from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from random import Random
from typing import Any, Callable, Generic, Protocol, TypeVar

try:
    from PySide6.QtCore import QTimer
except ImportError:  # pragma: no cover - exercised only when Qt is absent.
    QTimer = None  # type: ignore[assignment]


WordT = TypeVar("WordT")


class RandomIndexSource(Protocol):
    def __call__(self, max_exclusive: int) -> int: ...


@dataclass(slots=True, frozen=True)
class SchedulerSettings:
    enabled: bool = True
    min_delay_minutes: int = 8
    max_delay_minutes: int = 20
    busy_stop_threshold_seconds: int = 60
    activity_threshold_per_minute: int = 90
    activity_slowdown_weight: int = 100
    idle_multiplier_step_seconds: int = 60

    @classmethod
    def from_app_settings(cls, settings: Any) -> "SchedulerSettings":
        return normalize_scheduler_settings(
            cls(
                enabled=bool(getattr(settings, "enabled", True)),
                min_delay_minutes=int(getattr(settings, "min_delay_minutes", 8)),
                max_delay_minutes=int(getattr(settings, "max_delay_minutes", 20)),
                busy_stop_threshold_seconds=int(
                    getattr(settings, "busy_stop_threshold_seconds", 60)
                ),
                activity_threshold_per_minute=int(
                    getattr(settings, "activity_threshold_per_minute", 90)
                ),
                activity_slowdown_weight=int(
                    getattr(settings, "activity_slowdown_weight", 100)
                ),
                idle_multiplier_step_seconds=int(
                    getattr(settings, "idle_multiplier_step_seconds", 60)
                ),
            )
        )


@dataclass(slots=True, frozen=True)
class SchedulerState(Generic[WordT]):
    running: bool = False
    next_due_at: datetime | None = None
    queued_words: tuple[WordT, ...] = ()


class SchedulerActionKind(str, Enum):
    SHOW_WORD = "show_word"
    REQUEST_FRESH_WORD = "request_fresh_word"


@dataclass(slots=True, frozen=True)
class SchedulerAction(Generic[WordT]):
    kind: SchedulerActionKind
    reason: str
    word: WordT | None = None
    from_queue: bool = False


@dataclass(slots=True, frozen=True)
class EnqueueDecision(Generic[WordT]):
    accepted: bool
    queued_word: WordT | None


def normalize_scheduler_settings(settings: SchedulerSettings) -> SchedulerSettings:
    min_delay = max(1, settings.min_delay_minutes)
    max_delay = max(min_delay, settings.max_delay_minutes)
    busy_threshold = max(1, settings.busy_stop_threshold_seconds)
    activity_threshold = max(1, settings.activity_threshold_per_minute)
    activity_weight = max(0, settings.activity_slowdown_weight)
    idle_step = max(1, settings.idle_multiplier_step_seconds)
    return replace(
        settings,
        min_delay_minutes=min_delay,
        max_delay_minutes=max_delay,
        busy_stop_threshold_seconds=busy_threshold,
        activity_threshold_per_minute=activity_threshold,
        activity_slowdown_weight=activity_weight,
        idle_multiplier_step_seconds=idle_step,
    )


def random_base_delay_minutes(
    settings: SchedulerSettings,
    random_index: RandomIndexSource,
) -> int:
    normalized = normalize_scheduler_settings(settings)
    span = (normalized.max_delay_minutes - normalized.min_delay_minutes) + 1
    offset = max(0, min(random_index(span), span - 1))
    return normalized.min_delay_minutes + offset


def activity_delay_multiplier(
    activity_events_per_minute: float,
    settings: SchedulerSettings,
) -> float:
    normalized = normalize_scheduler_settings(settings)
    activity_ratio = max(0.0, activity_events_per_minute) / normalized.activity_threshold_per_minute
    if activity_ratio >= 1.5:
        base_multiplier = 4.0
    elif activity_ratio >= 0.75:
        base_multiplier = 2.0
    else:
        base_multiplier = 1.0
    weight = normalized.activity_slowdown_weight / 100.0
    return 1.0 + ((base_multiplier - 1.0) * weight)


def compute_next_delay(
    settings: SchedulerSettings,
    activity_events_per_minute: float,
    random_index: RandomIndexSource,
) -> timedelta | None:
    normalized = normalize_scheduler_settings(settings)
    if not normalized.enabled:
        return None

    multiplier = activity_delay_multiplier(activity_events_per_minute, normalized)
    base_delay_minutes = random_base_delay_minutes(normalized, random_index)
    return timedelta(minutes=base_delay_minutes * multiplier)


def utc_now() -> datetime:
    return datetime.now(UTC)


class SchedulerCore(Generic[WordT]):
    def __init__(
        self,
        settings: SchedulerSettings | None = None,
        *,
        random_index: RandomIndexSource | None = None,
    ) -> None:
        rng = Random()
        self._random_index = random_index or rng.randrange
        self._settings = normalize_scheduler_settings(settings or SchedulerSettings())
        self._state: SchedulerState[WordT] = SchedulerState()

    @property
    def settings(self) -> SchedulerSettings:
        return self._settings

    @property
    def next_due_at(self) -> datetime | None:
        return self._state.next_due_at

    @property
    def queued_word(self) -> WordT | None:
        return self._state.queued_words[0] if self._state.queued_words else None

    @property
    def state(self) -> SchedulerState[WordT]:
        return replace(self._state)

    def update_settings(self, settings: SchedulerSettings | Any) -> SchedulerSettings:
        normalized = (
            settings
            if isinstance(settings, SchedulerSettings)
            else SchedulerSettings.from_app_settings(settings)
        )
        self._settings = normalize_scheduler_settings(normalized)
        if not self._settings.enabled:
            self._state = replace(self._state, next_due_at=None)
        return self._settings

    def start(self, now: datetime, activity_events_per_minute: float) -> None:
        self._state = replace(self._state, running=True)
        self._ensure_next_due(now, activity_events_per_minute)

    def pause(self) -> None:
        self._state = replace(self._state, running=False, next_due_at=None)

    stop = pause

    def reset(self, now: datetime | None = None, activity_events_per_minute: float | None = None) -> None:
        self._state = replace(self._state, next_due_at=None)
        if self._state.running and now is not None and activity_events_per_minute is not None:
            self._ensure_next_due(now, activity_events_per_minute)

    def enqueue_word(self, word: WordT) -> EnqueueDecision[WordT]:
        queued_word = self.queued_word
        if queued_word is not None:
            return EnqueueDecision(accepted=False, queued_word=queued_word)

        self._state = replace(self._state, queued_words=(word,))
        return EnqueueDecision(accepted=True, queued_word=word)

    def enqueue_word_front(self, word: WordT) -> EnqueueDecision[WordT]:
        remaining_words = tuple(queued for queued in self._state.queued_words if queued != word)
        self._state = replace(self._state, queued_words=(word, *remaining_words))
        return EnqueueDecision(accepted=True, queued_word=word)

    def manual_request(self, word: WordT | None = None) -> SchedulerAction[WordT]:
        self._state = replace(self._state, next_due_at=None)
        if word is not None:
            return SchedulerAction(
                kind=SchedulerActionKind.SHOW_WORD,
                reason="manual",
                word=word,
                from_queue=False,
            )

        queued_word = self.queued_word
        if queued_word is not None:
            self._state = replace(self._state, queued_words=self._state.queued_words[1:])
            return SchedulerAction(
                kind=SchedulerActionKind.SHOW_WORD,
                reason="manual",
                word=queued_word,
                from_queue=True,
            )

        return SchedulerAction(
            kind=SchedulerActionKind.REQUEST_FRESH_WORD,
            reason="manual",
        )

    def on_timer(self, now: datetime, activity_events_per_minute: float) -> SchedulerAction[WordT] | None:
        if not self._state.running:
            return None

        if not self._settings.enabled:
            self._state = replace(self._state, next_due_at=None)
            return None

        if self._state.next_due_at is None:
            self._ensure_next_due(now, activity_events_per_minute)
            return None

        if now < self._state.next_due_at:
            return None

        self._state = replace(self._state, next_due_at=None)
        queued_word = self.queued_word
        if queued_word is not None:
            self._state = replace(self._state, queued_words=self._state.queued_words[1:])
            return SchedulerAction(
                kind=SchedulerActionKind.SHOW_WORD,
                reason="automatic",
                word=queued_word,
                from_queue=True,
            )

        return SchedulerAction(
            kind=SchedulerActionKind.REQUEST_FRESH_WORD,
            reason="automatic",
        )

    def _ensure_next_due(self, now: datetime, activity_events_per_minute: float) -> None:
        if self._state.next_due_at is not None:
            return

        delay = compute_next_delay(self._settings, activity_events_per_minute, self._random_index)
        if delay is None:
            return

        self._state = replace(self._state, next_due_at=now + delay)


class QtScheduler(Generic[WordT]):
    def __init__(
        self,
        *,
        settings_provider: Callable[[], Any],
        activity_rate_provider: Callable[[], float],
        emit_action: Callable[[SchedulerAction[WordT]], None],
        now_provider: Callable[[], datetime] = utc_now,
        interval_ms: int = 3000,
        random_index: RandomIndexSource | None = None,
        timer: QTimer | None = None,
    ) -> None:
        if timer is None and QTimer is None:
            raise RuntimeError("PySide6 is required to create a QtScheduler timer.")

        self._settings_provider = settings_provider
        self._activity_rate_provider = activity_rate_provider
        self._emit_action = emit_action
        self._now_provider = now_provider
        self._core: SchedulerCore[WordT] = SchedulerCore(random_index=random_index)
        self._timer = timer or QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.handle_timer_timeout)

    @property
    def next_due_at(self) -> datetime | None:
        return self._core.next_due_at

    @property
    def queued_word(self) -> WordT | None:
        return self._core.queued_word

    @property
    def state(self) -> SchedulerState[WordT]:
        return self._core.state

    def start(self) -> None:
        self._refresh_settings()
        self._core.start(self._now_provider(), self._activity_rate_provider())
        if not self._timer.isActive():
            self._timer.start()

    def pause(self) -> None:
        self._core.pause()
        self._timer.stop()

    stop = pause

    def reset(self) -> None:
        self._refresh_settings()
        self._core.reset(self._now_provider(), self._activity_rate_provider())

    def manual_request(self, word: WordT | None = None) -> SchedulerAction[WordT]:
        self._refresh_settings()
        action = self._core.manual_request(word)
        self._emit_action(action)
        return action

    def enqueue_word(self, word: WordT) -> EnqueueDecision[WordT]:
        return self._core.enqueue_word(word)

    def enqueue_word_front(self, word: WordT) -> EnqueueDecision[WordT]:
        return self._core.enqueue_word_front(word)

    def handle_timer_timeout(self) -> SchedulerAction[WordT] | None:
        self._refresh_settings()
        action = self._core.on_timer(self._now_provider(), self._activity_rate_provider())
        if action is not None:
            self._emit_action(action)
        return action

    def dispose(self) -> None:
        self._timer.stop()
        try:
            self._timer.timeout.disconnect(self.handle_timer_timeout)
        except (RuntimeError, TypeError):
            pass

    def _refresh_settings(self) -> SchedulerSettings:
        return self._core.update_settings(self._settings_provider())
