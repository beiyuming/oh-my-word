from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.scheduler import (
    EnqueueDecision,
    SchedulerActionKind,
    SchedulerCore,
    SchedulerSettings,
    compute_next_delay,
    idle_delay_multiplier,
    random_base_delay_minutes,
)


class SchedulerHelpersTests(unittest.TestCase):
    def test_random_base_delay_is_within_bounds(self) -> None:
        settings = SchedulerSettings(min_delay_minutes=8, max_delay_minutes=20)

        delay = random_base_delay_minutes(settings, lambda max_exclusive: max_exclusive - 1)

        self.assertEqual(delay, 20)

    def test_idle_multiplier_grows_monotonically_after_threshold(self) -> None:
        settings = SchedulerSettings(busy_stop_threshold_seconds=8, idle_multiplier_step_seconds=10)

        self.assertEqual(idle_delay_multiplier(7, settings), 0)
        self.assertEqual(idle_delay_multiplier(8, settings), 4)
        self.assertEqual(idle_delay_multiplier(18, settings), 2)
        self.assertEqual(idle_delay_multiplier(28, settings), 1)

    def test_compute_next_delay_returns_none_below_busy_threshold(self) -> None:
        settings = SchedulerSettings(busy_stop_threshold_seconds=8)

        self.assertIsNone(compute_next_delay(settings, 4, lambda _: 0))


class SchedulerCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SchedulerSettings(
            enabled=True,
            min_delay_minutes=8,
            max_delay_minutes=8,
            busy_stop_threshold_seconds=8,
            idle_multiplier_step_seconds=10,
        )
        self.now = datetime(2026, 5, 29, 10, 0, tzinfo=UTC)

    def test_manual_request_bypasses_busy_gate(self) -> None:
        core = SchedulerCore[str](self.settings, random_index=lambda _: 0)

        action = core.manual_request()

        self.assertEqual(action.kind, SchedulerActionKind.REQUEST_FRESH_WORD)
        self.assertEqual(action.reason, "manual")

    def test_enqueue_keeps_first_queued_word(self) -> None:
        core = SchedulerCore[str](self.settings, random_index=lambda _: 0)

        first = core.enqueue_word("alpha")
        second = core.enqueue_word("beta")

        self.assertEqual(first, EnqueueDecision(accepted=True, queued_word="alpha"))
        self.assertEqual(second, EnqueueDecision(accepted=False, queued_word="alpha"))

    def test_timer_consumes_queued_word_before_requesting_fresh_word(self) -> None:
        core = SchedulerCore[str](self.settings, random_index=lambda _: 0)
        core.start(self.now, idle_seconds=30)
        core.enqueue_word("alpha")

        action = core.on_timer(self.now + timedelta(minutes=8), idle_seconds=30)

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.kind, SchedulerActionKind.SHOW_WORD)
        self.assertEqual(action.word, "alpha")
        self.assertTrue(action.from_queue)
        self.assertIsNone(core.queued_word)

    def test_timer_requests_fresh_word_when_due_without_queue(self) -> None:
        core = SchedulerCore[str](self.settings, random_index=lambda _: 0)
        core.start(self.now, idle_seconds=30)

        action = core.on_timer(self.now + timedelta(minutes=8), idle_seconds=30)

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.kind, SchedulerActionKind.REQUEST_FRESH_WORD)
        self.assertEqual(action.reason, "automatic")


if __name__ == "__main__":
    unittest.main()
