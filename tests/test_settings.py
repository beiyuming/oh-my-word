from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import Accent, AppSettings, DisplayMode, LearningState, OverlayPosition, WordProgress
from app.settings import LearningStateStore, SettingsStore, setup_app_logger


@dataclass(slots=True)
class _TestPaths:
    root_dir: Path
    data_dir: Path
    wordbooks_dir: Path
    storage_dir: Path
    settings_path: Path
    learning_state_path: Path
    log_path: Path


def make_paths(tmp_dir: str) -> _TestPaths:
    root_dir = Path(tmp_dir) / "root"
    root_dir.mkdir()
    data_dir = root_dir / "data"
    wordbooks_dir = data_dir / "wordbooks"
    storage_dir = root_dir / "storage"
    return _TestPaths(
        root_dir=root_dir,
        data_dir=data_dir,
        wordbooks_dir=wordbooks_dir,
        storage_dir=storage_dir,
        settings_path=storage_dir / "settings.json",
        learning_state_path=storage_dir / "learning_state.json",
        log_path=storage_dir / "app.log",
    )


class SettingsStoreTests(unittest.TestCase):
    def test_loads_defaults_when_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)

            settings = SettingsStore(paths).load()

            self.assertEqual(settings, AppSettings())
            self.assertFalse(paths.settings_path.exists())

    def test_normalizes_invalid_values(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text(
                json.dumps(
                    {
                        "enabled": "yes",
                        "display_mode": "invalid",
                        "card_position": "center",
                        "barrage_position": "sideways",
                        "min_delay_minutes": -4,
                        "max_delay_minutes": 0,
                        "busy_stop_threshold_seconds": "oops",
                        "activity_threshold_per_minute": 0,
                        "activity_slowdown_weight": -1,
                        "popup_duration_seconds": -3,
                        "snooze_minutes": 0,
                        "mute_pronunciation": "no",
                        "accent": "AU",
                        "pronounce_hotkey": "",
                        "toggle_detail_hotkey": None,
                        "trigger_now_hotkey": "Alt+9",
                        "mark_mastered_hotkey": "",
                        "known_hotkey": "",
                        "unknown_hotkey": 12,
                        "dismiss_hotkey": "",
                    }
                ),
                encoding="utf-8",
            )

            settings = SettingsStore(paths).load()

            self.assertTrue(settings.enabled)
            self.assertIs(settings.display_mode, DisplayMode.CARD)
            self.assertIs(settings.card_position, OverlayPosition.CENTER)
            self.assertIs(settings.barrage_position, OverlayPosition.TOP_CENTER)
            self.assertEqual(settings.min_delay_minutes, 8)
            self.assertEqual(settings.max_delay_minutes, 20)
            self.assertEqual(settings.busy_stop_threshold_seconds, 8)
            self.assertEqual(settings.activity_threshold_per_minute, 90)
            self.assertEqual(settings.activity_slowdown_weight, 100)
            self.assertEqual(settings.popup_duration_seconds, 6)
            self.assertEqual(settings.snooze_minutes, 30)
            self.assertFalse(settings.mute_pronunciation)
            self.assertIs(settings.accent, Accent.US)
            self.assertEqual(settings.pronounce_hotkey, "Ctrl+Alt+1")
            self.assertEqual(settings.toggle_detail_hotkey, "Ctrl+Alt+2")
            self.assertEqual(settings.trigger_now_hotkey, "Alt+9")
            self.assertEqual(settings.mark_mastered_hotkey, "Ctrl+Alt+4")
            self.assertEqual(settings.known_hotkey, "Ctrl+Alt+5")
            self.assertEqual(settings.unknown_hotkey, "Ctrl+Alt+6")
            self.assertEqual(settings.dismiss_hotkey, "Ctrl+Alt+7")

    def test_persists_pretty_utf8_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            store = SettingsStore(paths)
            settings = AppSettings(min_delay_minutes=7, max_delay_minutes=11)

            reloaded = store.save(settings)

            raw = paths.settings_path.read_text(encoding="utf-8")
            self.assertIn('\n  "enabled": true,', raw)
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(reloaded, settings)

    def test_loads_random_barrage_position(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text(
                json.dumps({"barrage_position": "random"}),
                encoding="utf-8",
            )

            settings = SettingsStore(paths).load()

            self.assertIs(settings.barrage_position, OverlayPosition.RANDOM)

    def test_loads_random_card_position(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text(
                json.dumps({"card_position": "random"}),
                encoding="utf-8",
            )

            settings = SettingsStore(paths).load()

            self.assertIs(settings.card_position, OverlayPosition.RANDOM)

    def test_persists_new_popup_action_hotkeys(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            store = SettingsStore(paths)
            settings = AppSettings(
                known_hotkey="Ctrl+Alt+8",
                unknown_hotkey="Ctrl+Alt+9",
                dismiss_hotkey="Ctrl+Alt+0",
            )

            reloaded = store.save(settings)
            payload = json.loads(paths.settings_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["known_hotkey"], "Ctrl+Alt+8")
            self.assertEqual(payload["unknown_hotkey"], "Ctrl+Alt+9")
            self.assertEqual(payload["dismiss_hotkey"], "Ctrl+Alt+0")
            self.assertEqual(reloaded.known_hotkey, "Ctrl+Alt+8")
            self.assertEqual(reloaded.unknown_hotkey, "Ctrl+Alt+9")
            self.assertEqual(reloaded.dismiss_hotkey, "Ctrl+Alt+0")

    def test_persists_snooze_minutes(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            store = SettingsStore(paths)
            settings = AppSettings(snooze_minutes=45)

            reloaded = store.save(settings)
            payload = json.loads(paths.settings_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["snooze_minutes"], 45)
            self.assertEqual(reloaded.snooze_minutes, 45)

    def test_recovers_from_corrupted_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text("{bad json", encoding="utf-8")

            settings = SettingsStore(paths).load()

            self.assertEqual(settings, AppSettings())


class LearningStateStoreTests(unittest.TestCase):
    def test_round_trips_recent_words_and_mastered_flag(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            store = LearningStateStore(paths)
            state = LearningState(
                recent_words=["abandon", "derive"],
                progress={
                    "abandon": WordProgress(
                        show_count=3,
                        last_shown_at="2026-05-29T10:20:00+08:00",
                        last_pronounced_at="2026-05-29T10:20:03+08:00",
                        last_expanded_at="2026-05-29T10:20:05+08:00",
                        mastered=True,
                    )
                },
            )

            reloaded = store.save(state)

            self.assertEqual(reloaded, state)
            self.assertEqual(store.load(), state)

    def test_normalizes_invalid_payloads(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.learning_state_path.write_text(
                json.dumps(
                    {
                        "recent_words": ["focus", 3, ""],
                        "progress": {
                            "focus": {
                                "show_count": -1,
                                "last_shown_at": 12,
                                "mastered": "yes",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            state = LearningStateStore(paths).load()

            self.assertEqual(state.recent_words, ["focus"])
            self.assertEqual(state.progress["focus"].show_count, 0)
            self.assertIsNone(state.progress["focus"].last_shown_at)
            self.assertFalse(state.progress["focus"].mastered)


class LoggerTests(unittest.TestCase):
    def test_bootstraps_rotating_log(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            logger = setup_app_logger(paths)
            logger.info("first line")

            for handler in logger.handlers:
                handler.flush()

            self.assertTrue(paths.log_path.exists())
            self.assertIn("first line", paths.log_path.read_text(encoding="utf-8"))

            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
