from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.scheduler import (
    EnqueueDecision,
    SchedulerActionKind,
    SchedulerCore,
    SchedulerSettings,
    activity_delay_multiplier,
    compute_next_delay,
    random_base_delay_minutes,
)


class SchedulerHelpersTests(unittest.TestCase):
    def test_random_base_delay_is_within_bounds(self) -> None:
        settings = SchedulerSettings(min_delay_minutes=8, max_delay_minutes=20)

        delay = random_base_delay_minutes(settings, lambda max_exclusive: max_exclusive - 1)

        self.assertEqual(delay, 20)

    def test_activity_multiplier_slows_down_high_frequency_operation(self) -> None:
        settings = SchedulerSettings(activity_threshold_per_minute=100)

        self.assertEqual(activity_delay_multiplier(74, settings), 1)
        self.assertEqual(activity_delay_multiplier(75, settings), 2)
        self.assertEqual(activity_delay_multiplier(149, settings), 2)
        self.assertEqual(activity_delay_multiplier(150, settings), 4)

    def test_activity_multiplier_honors_slowdown_weight(self) -> None:
        disabled = SchedulerSettings(activity_threshold_per_minute=100, activity_slowdown_weight=0)
        softened = SchedulerSettings(activity_threshold_per_minute=100, activity_slowdown_weight=50)
        amplified = SchedulerSettings(activity_threshold_per_minute=100, activity_slowdown_weight=200)

        self.assertEqual(activity_delay_multiplier(180, disabled), 1)
        self.assertEqual(activity_delay_multiplier(180, softened), 2.5)
        self.assertEqual(activity_delay_multiplier(180, amplified), 7)

    def test_compute_next_delay_never_blocks_only_slows_down_for_activity(self) -> None:
        settings = SchedulerSettings(min_delay_minutes=8, max_delay_minutes=8, activity_threshold_per_minute=100)

        self.assertEqual(compute_next_delay(settings, 0, lambda _: 0), timedelta(minutes=8))
        self.assertEqual(compute_next_delay(settings, 90, lambda _: 0), timedelta(minutes=16))
        self.assertEqual(compute_next_delay(settings, 180, lambda _: 0), timedelta(minutes=32))


class SchedulerCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SchedulerSettings(
            enabled=True,
            min_delay_minutes=8,
            max_delay_minutes=8,
            activity_threshold_per_minute=90,
        )
        self.now = datetime(2026, 5, 29, 10, 0, tzinfo=UTC)

    def test_manual_request_bypasses_schedule(self) -> None:
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

    def test_enqueue_word_front_preempts_existing_queue_without_losing_it(self) -> None:
        core = SchedulerCore[str](self.settings, random_index=lambda _: 0)
        core.enqueue_word("beta")

        decision = core.enqueue_word_front("alpha")
        first_action = core.manual_request()
        second_action = core.manual_request()

        self.assertEqual(decision, EnqueueDecision(accepted=True, queued_word="alpha"))
        self.assertEqual(first_action.word, "alpha")
        self.assertTrue(first_action.from_queue)
        self.assertEqual(second_action.word, "beta")
        self.assertTrue(second_action.from_queue)

    def test_timer_consumes_queued_word_before_requesting_fresh_word(self) -> None:
        core = SchedulerCore[str](self.settings, random_index=lambda _: 0)
        core.start(self.now, activity_events_per_minute=30)
        core.enqueue_word("alpha")

        action = core.on_timer(self.now + timedelta(minutes=8), activity_events_per_minute=30)

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.kind, SchedulerActionKind.SHOW_WORD)
        self.assertEqual(action.word, "alpha")
        self.assertTrue(action.from_queue)
        self.assertIsNone(core.queued_word)

    def test_timer_requests_fresh_word_when_due_without_queue(self) -> None:
        core = SchedulerCore[str](self.settings, random_index=lambda _: 0)
        core.start(self.now, activity_events_per_minute=30)

        action = core.on_timer(self.now + timedelta(minutes=8), activity_events_per_minute=30)

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.kind, SchedulerActionKind.REQUEST_FRESH_WORD)
        self.assertEqual(action.reason, "automatic")


if __name__ == "__main__":
    unittest.main()
