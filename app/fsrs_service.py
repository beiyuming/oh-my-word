from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from fsrs import Card, Rating, Scheduler


class ProjectReviewRating(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class FsrsReviewResult:
    due_at: str | None
    state: str
    stability: float | None
    difficulty: float | None
    scheduled_days: int | None
    elapsed_days: int | None
    last_rating: str
    fsrs_card_json: str
    fsrs_review_log_json: str


class FsrsReviewService:
    def __init__(self, scheduler: Scheduler | None = None) -> None:
        self._scheduler = scheduler or Scheduler()

    def review(
        self,
        fsrs_card_json: str | None,
        rating: ProjectReviewRating,
        *,
        reviewed_at: datetime,
    ) -> FsrsReviewResult:
        card = self._load_card(fsrs_card_json)
        fsrs_rating = Rating.Good if rating is ProjectReviewRating.KNOWN else Rating.Again
        reviewed_card, review_log = self._scheduler.review_card(
            card,
            fsrs_rating,
            review_datetime=reviewed_at,
        )
        card_payload = reviewed_card.to_dict()
        log_payload = review_log.to_dict()
        return FsrsReviewResult(
            due_at=_iso_or_none(card_payload.get("due")),
            state=str(card_payload.get("state", "")),
            stability=_float_or_none(card_payload.get("stability")),
            difficulty=_float_or_none(card_payload.get("difficulty")),
            scheduled_days=_int_or_none(log_payload.get("scheduled_days")),
            elapsed_days=_int_or_none(log_payload.get("elapsed_days")),
            last_rating=rating.value,
            fsrs_card_json=json.dumps(card_payload, ensure_ascii=False, sort_keys=True, default=str),
            fsrs_review_log_json=json.dumps(log_payload, ensure_ascii=False, sort_keys=True, default=str),
        )

    @staticmethod
    def _load_card(payload: str | None) -> Card:
        if not payload:
            return Card()
        return Card.from_dict(json.loads(payload))


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
