from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from .models import WordProgress


def apply_review_result(
    progress: WordProgress,
    *,
    known: bool,
    reviewed_at: datetime | None = None,
) -> WordProgress:
    now = reviewed_at or datetime.now(UTC)
    current_stability = max(0.0, progress.stability)
    current_difficulty = _clamp(progress.difficulty or 5.0, 1.0, 10.0)

    if known:
        stability = _next_known_stability(current_stability, current_difficulty, progress.review_count)
        difficulty = _clamp(current_difficulty - 0.35, 1.0, 10.0)
        due_at = now + timedelta(days=stability)
        return replace(
            progress,
            last_reviewed_at=now.isoformat(),
            due_at=due_at.isoformat(),
            review_count=progress.review_count + 1,
            known_count=progress.known_count + 1,
            stability=stability,
            difficulty=difficulty,
            last_rating="known",
            mastered=False,
        )

    stability = max(0.1, current_stability * 0.45) if current_stability > 0 else 0.1
    difficulty = _clamp(current_difficulty + 0.85, 1.0, 10.0)
    due_at = now + timedelta(minutes=10)
    return replace(
        progress,
        last_reviewed_at=now.isoformat(),
        due_at=due_at.isoformat(),
        review_count=progress.review_count + 1,
        unknown_count=progress.unknown_count + 1,
        stability=stability,
        difficulty=difficulty,
        last_rating="unknown",
        mastered=False,
    )


def is_due(progress: WordProgress, now: datetime | None = None) -> bool:
    if progress.due_at is None:
        return False
    due_at = _parse_datetime(progress.due_at)
    if due_at is None:
        return True
    return due_at <= (now or datetime.now(UTC))


def _next_known_stability(current_stability: float, difficulty: float, review_count: int) -> float:
    if current_stability <= 0 or review_count <= 0:
        return 1.0
    growth = 1.0 + max(0.15, (11.0 - difficulty) * 0.12)
    return min(365.0, max(current_stability + 0.5, current_stability * growth))


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
