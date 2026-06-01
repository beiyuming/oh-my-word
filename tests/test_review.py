from __future__ import annotations

import unittest
from datetime import UTC, datetime

from app.models import WordProgress
from app.review import apply_review_result, is_due


class ReviewTests(unittest.TestCase):
    def test_known_review_schedules_future_review_and_lowers_difficulty(self) -> None:
        now = datetime(2026, 5, 30, 10, 0, tzinfo=UTC)

        updated = apply_review_result(WordProgress(difficulty=5.0), known=True, reviewed_at=now)

        self.assertEqual(1, updated.review_count)
        self.assertEqual(1, updated.known_count)
        self.assertEqual("known", updated.last_rating)
        self.assertGreater(updated.stability, 0)
        self.assertLess(updated.difficulty, 5.0)
        self.assertFalse(is_due(updated, now))

    def test_unknown_review_schedules_near_review_and_raises_difficulty(self) -> None:
        now = datetime(2026, 5, 30, 10, 0, tzinfo=UTC)

        updated = apply_review_result(WordProgress(stability=4.0, difficulty=5.0), known=False, reviewed_at=now)

        self.assertEqual(1, updated.review_count)
        self.assertEqual(1, updated.unknown_count)
        self.assertEqual("unknown", updated.last_rating)
        self.assertLess(updated.stability, 4.0)
        self.assertGreater(updated.difficulty, 5.0)
        self.assertFalse(is_due(updated, now))


if __name__ == "__main__":
    unittest.main()
