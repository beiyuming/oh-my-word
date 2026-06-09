from __future__ import annotations

from datetime import UTC, datetime

from app.fsrs_service import FsrsReviewService, ProjectReviewRating


def test_known_review_maps_to_good_and_returns_due_state() -> None:
    service = FsrsReviewService()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)

    result = service.review(None, ProjectReviewRating.KNOWN, reviewed_at=now)

    assert result.last_rating == "known"
    assert result.due_at is not None
    assert result.stability is None or result.stability >= 0
    assert result.difficulty is None or result.difficulty > 0
    assert result.fsrs_card_json
    assert result.fsrs_review_log_json


def test_unknown_review_maps_to_again_and_returns_due_state() -> None:
    service = FsrsReviewService()
    now = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)

    result = service.review(None, ProjectReviewRating.UNKNOWN, reviewed_at=now)

    assert result.last_rating == "unknown"
    assert result.due_at is not None
    assert result.fsrs_card_json
    assert result.fsrs_review_log_json
