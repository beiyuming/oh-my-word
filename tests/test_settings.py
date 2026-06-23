from __future__ import annotations

import json
import os
import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import (
    Accent,
    AppSettings,
    DEFAULT_VOXCPM_CFG_VALUE,
    DEFAULT_VOXCPM_DEVICE,
    DEFAULT_VOXCPM_INFERENCE_TIMESTEPS,
    DEFAULT_VOXCPM_INSTALL_ROOT,
    DEFAULT_VOXCPM_LEADING_SILENCE_SECONDS,
    DEFAULT_VOXCPM_MODEL_CACHE_ROOT,
    DEFAULT_VOXCPM_MODELSCOPE_MIN_DRIVER_VERSION,
    DEFAULT_VOXCPM_MODELSCOPE_NAMESPACE,
    DEFAULT_VOXCPM_MODELSCOPE_REPOSITORY,
    DEFAULT_VOXCPM_MODELSCOPE_RUNTIME_FILENAME,
    DEFAULT_VOXCPM_OPTIMIZE,
    DEFAULT_VOXCPM_RETRY_BADCASE,
    DEFAULT_VOXCPM_RETRY_BADCASE_MAX_TIMES,
    DEFAULT_VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD,
    DEFAULT_VOXCPM_STREAM_PREBUFFER_MAX_WAIT_SECONDS,
    DEFAULT_VOXCPM_TRAILING_SILENCE_SECONDS,
    DisplayMode,
    LearningState,
    OverlayPosition,
    PronunciationContentMode,
    TtsProvider,
    VoxCpmDevice,
    WordProgress,
)
from app.settings import LearningStateStore, SettingsStore, settings_to_dict, setup_app_logger


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
    def test_tts_provider_defaults_to_system_qt(self) -> None:
        settings = AppSettings()

        self.assertIs(settings.tts_provider, TtsProvider.SYSTEM_QT)
        self.assertFalse(settings.auto_pronounce_on_popup)
        self.assertEqual(settings.auto_pronounce_delay_seconds, 1.0)
        self.assertEqual(settings.voxcpm_endpoint, "http://127.0.0.1:8808")
        self.assertEqual(settings.voxcpm_timeout_seconds, 15)
        self.assertIn(str(Path("OhMyWord") / "tts" / "voxcpm"), DEFAULT_VOXCPM_INSTALL_ROOT)
        self.assertEqual(settings.voxcpm_install_root, DEFAULT_VOXCPM_INSTALL_ROOT)
        self.assertEqual(settings.voxcpm_model_cache_root, DEFAULT_VOXCPM_MODEL_CACHE_ROOT)
        self.assertEqual(settings.voxcpm_model_cache_root, str(Path(settings.voxcpm_install_root) / "models"))
        self.assertTrue(settings.voxcpm_use_model_mirror)
        self.assertFalse(settings.voxcpm_auto_start)
        self.assertEqual(settings.voxcpm_voice_prompt, "")
        self.assertEqual(settings.voxcpm_modelscope_namespace, DEFAULT_VOXCPM_MODELSCOPE_NAMESPACE)
        self.assertEqual(settings.voxcpm_modelscope_repository, DEFAULT_VOXCPM_MODELSCOPE_REPOSITORY)
        self.assertEqual(settings.voxcpm_modelscope_runtime_filename, DEFAULT_VOXCPM_MODELSCOPE_RUNTIME_FILENAME)
        self.assertEqual(settings.voxcpm_modelscope_min_driver_version, DEFAULT_VOXCPM_MODELSCOPE_MIN_DRIVER_VERSION)
        self.assertEqual(settings.voxcpm_stream_prebuffer_seconds, 0.35)
        self.assertIs(settings.voxcpm_device, DEFAULT_VOXCPM_DEVICE)
        self.assertEqual(settings.voxcpm_optimize, DEFAULT_VOXCPM_OPTIMIZE)
        self.assertEqual(settings.voxcpm_cfg_value, DEFAULT_VOXCPM_CFG_VALUE)
        self.assertEqual(settings.voxcpm_inference_timesteps, DEFAULT_VOXCPM_INFERENCE_TIMESTEPS)
        self.assertEqual(settings.voxcpm_retry_badcase, DEFAULT_VOXCPM_RETRY_BADCASE)
        self.assertEqual(settings.voxcpm_retry_badcase_max_times, DEFAULT_VOXCPM_RETRY_BADCASE_MAX_TIMES)
        self.assertEqual(
            settings.voxcpm_retry_badcase_ratio_threshold,
            DEFAULT_VOXCPM_RETRY_BADCASE_RATIO_THRESHOLD,
        )
        self.assertEqual(settings.voxcpm_leading_silence_seconds, DEFAULT_VOXCPM_LEADING_SILENCE_SECONDS)
        self.assertEqual(settings.voxcpm_trailing_silence_seconds, DEFAULT_VOXCPM_TRAILING_SILENCE_SECONDS)
        self.assertEqual(
            settings.voxcpm_stream_prebuffer_max_wait_seconds,
            DEFAULT_VOXCPM_STREAM_PREBUFFER_MAX_WAIT_SECONDS,
        )
        self.assertIs(settings.pronunciation_content_mode, PronunciationContentMode.WORD_AND_EXAMPLE)

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
                        "auto_pronounce_on_popup": "yes",
                        "auto_pronounce_delay_seconds": -1,
                        "mute_pronunciation": "no",
                        "pronunciation_content_mode": "invalid",
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
            self.assertFalse(settings.auto_pronounce_on_popup)
            self.assertEqual(settings.auto_pronounce_delay_seconds, 1.0)
            self.assertFalse(settings.mute_pronunciation)
            self.assertIs(
                settings.pronunciation_content_mode,
                PronunciationContentMode.WORD_AND_EXAMPLE,
            )
            self.assertIs(settings.accent, Accent.US)
            self.assertEqual(settings.pronounce_hotkey, "Ctrl+Alt+1")
            self.assertEqual(settings.toggle_detail_hotkey, "Ctrl+Alt+2")
            self.assertEqual(settings.trigger_now_hotkey, "Alt+9")
            self.assertEqual(settings.mark_mastered_hotkey, "Ctrl+Alt+4")
            self.assertEqual(settings.known_hotkey, "Ctrl+Alt+5")
            self.assertEqual(settings.unknown_hotkey, "Ctrl+Alt+6")
            self.assertEqual(settings.dismiss_hotkey, "Ctrl+Alt+7")

    def test_normalizes_tts_provider_settings(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text(
                json.dumps(
                    {
                        "tts_provider": "voxcpm_local",
                        "auto_pronounce_on_popup": True,
                        "auto_pronounce_delay_seconds": 1.25,
                        "pronunciation_content_mode": "example",
                        "voxcpm_endpoint": "http://localhost:8808/",
                        "voxcpm_timeout_seconds": 31,
                        "voxcpm_install_root": "%LOCALAPPDATA%\\OhMyWord\\custom-voxcpm",
                        "voxcpm_model_cache_root": "D:\\Models\\VoxCPM2",
                        "voxcpm_use_model_mirror": False,
                        "voxcpm_auto_start": True,
                        "voxcpm_voice_prompt": "  A calm English teacher voice.  ",
                        "voxcpm_modelscope_namespace": "borealis",
                        "voxcpm_modelscope_repository": "oh-my-word-voxcpm2-runtime",
                        "voxcpm_modelscope_runtime_filename": "voxcpm2-runtime-win-x64-cu130-r2.zip",
                        "voxcpm_modelscope_min_driver_version": "581",
                        "voxcpm_stream_prebuffer_seconds": 0.8,
                        "voxcpm_device": "cuda",
                        "voxcpm_optimize": True,
                        "voxcpm_cfg_value": 2.25,
                        "voxcpm_inference_timesteps": 18,
                        "voxcpm_retry_badcase": False,
                        "voxcpm_retry_badcase_max_times": 5,
                        "voxcpm_retry_badcase_ratio_threshold": 3.5,
                        "voxcpm_leading_silence_seconds": 0.2,
                        "voxcpm_trailing_silence_seconds": 0.45,
                        "voxcpm_stream_prebuffer_max_wait_seconds": 1.25,
                    }
                ),
                encoding="utf-8",
            )

            settings = SettingsStore(paths).load()

            self.assertIs(settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
            self.assertTrue(settings.auto_pronounce_on_popup)
            self.assertEqual(settings.auto_pronounce_delay_seconds, 1.25)
            self.assertIs(settings.pronunciation_content_mode, PronunciationContentMode.EXAMPLE)
            self.assertEqual(settings.voxcpm_endpoint, "http://localhost:8808")
            self.assertEqual(settings.voxcpm_timeout_seconds, 31)
            self.assertEqual(
                settings.voxcpm_install_root,
                str(Path(os.path.expandvars("%LOCALAPPDATA%\\OhMyWord\\custom-voxcpm"))),
            )
            self.assertEqual(settings.voxcpm_model_cache_root, str(Path("D:\\Models\\VoxCPM2")))
            self.assertFalse(settings.voxcpm_use_model_mirror)
            self.assertTrue(settings.voxcpm_auto_start)
            self.assertEqual(settings.voxcpm_voice_prompt, "A calm English teacher voice.")
            self.assertEqual(settings.voxcpm_modelscope_namespace, "borealis")
            self.assertEqual(settings.voxcpm_modelscope_repository, "oh-my-word-voxcpm2-runtime")
            self.assertEqual(settings.voxcpm_modelscope_runtime_filename, "voxcpm2-runtime-win-x64-cu130-r2.zip")
            self.assertEqual(settings.voxcpm_modelscope_min_driver_version, "581")
            self.assertEqual(settings.voxcpm_stream_prebuffer_seconds, 0.8)
            self.assertIs(settings.voxcpm_device, VoxCpmDevice.CUDA)
            self.assertTrue(settings.voxcpm_optimize)
            self.assertEqual(settings.voxcpm_cfg_value, 2.25)
            self.assertEqual(settings.voxcpm_inference_timesteps, 18)
            self.assertFalse(settings.voxcpm_retry_badcase)
            self.assertEqual(settings.voxcpm_retry_badcase_max_times, 5)
            self.assertEqual(settings.voxcpm_retry_badcase_ratio_threshold, 3.5)
            self.assertEqual(settings.voxcpm_leading_silence_seconds, 0.2)
            self.assertEqual(settings.voxcpm_trailing_silence_seconds, 0.45)
            self.assertEqual(settings.voxcpm_stream_prebuffer_max_wait_seconds, 1.25)

    def test_rejects_non_local_voxcpm_endpoint(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            paths = make_paths(tmp_dir)
            paths.storage_dir.mkdir(parents=True, exist_ok=True)
            paths.settings_path.write_text(
                json.dumps(
                    {
                        "tts_provider": "voxcpm_local",
                        "auto_pronounce_on_popup": 1,
                        "auto_pronounce_delay_seconds": 20,
                        "voxcpm_endpoint": "https://example.com/tts",
                        "voxcpm_timeout_seconds": 0,
                        "voxcpm_install_root": "",
                        "voxcpm_model_cache_root": [],
                        "voxcpm_use_model_mirror": "yes",
                        "voxcpm_auto_start": 1,
                        "voxcpm_voice_prompt": [],
                        "voxcpm_modelscope_namespace": "",
                        "voxcpm_modelscope_repository": [],
                        "voxcpm_modelscope_runtime_filename": {},
                        "voxcpm_modelscope_min_driver_version": None,
                        "voxcpm_stream_prebuffer_seconds": -1,
                        "voxcpm_device": "gpu",
                        "voxcpm_optimize": "yes",
                        "voxcpm_cfg_value": -2.0,
                        "voxcpm_inference_timesteps": 0,
                        "voxcpm_retry_badcase": 1,
                        "voxcpm_retry_badcase_max_times": -1,
                        "voxcpm_retry_badcase_ratio_threshold": 99.0,
                        "voxcpm_leading_silence_seconds": -0.5,
                        "voxcpm_trailing_silence_seconds": 9.0,
                        "voxcpm_stream_prebuffer_max_wait_seconds": 0,
                    }
                ),
                encoding="utf-8",
            )

            settings = SettingsStore(paths).load()

            self.assertIs(settings.tts_provider, TtsProvider.VOXCPM_LOCAL)
            self.assertFalse(settings.auto_pronounce_on_popup)
            self.assertEqual(settings.auto_pronounce_delay_seconds, 10.0)
            self.assertEqual(settings.voxcpm_endpoint, "http://127.0.0.1:8808")
            self.assertEqual(settings.voxcpm_timeout_seconds, 15)
            self.assertEqual(settings.voxcpm_install_root, DEFAULT_VOXCPM_INSTALL_ROOT)
            self.assertEqual(settings.voxcpm_model_cache_root, DEFAULT_VOXCPM_MODEL_CACHE_ROOT)
            self.assertTrue(settings.voxcpm_use_model_mirror)
            self.assertFalse(settings.voxcpm_auto_start)
            self.assertEqual(settings.voxcpm_voice_prompt, "")
            self.assertEqual(settings.voxcpm_modelscope_namespace, DEFAULT_VOXCPM_MODELSCOPE_NAMESPACE)
            self.assertEqual(settings.voxcpm_modelscope_repository, DEFAULT_VOXCPM_MODELSCOPE_REPOSITORY)
            self.assertEqual(settings.voxcpm_modelscope_runtime_filename, DEFAULT_VOXCPM_MODELSCOPE_RUNTIME_FILENAME)
            self.assertEqual(settings.voxcpm_modelscope_min_driver_version, DEFAULT_VOXCPM_MODELSCOPE_MIN_DRIVER_VERSION)
            self.assertEqual(settings.voxcpm_stream_prebuffer_seconds, 0.35)
            self.assertIs(settings.voxcpm_device, DEFAULT_VOXCPM_DEVICE)
            self.assertEqual(settings.voxcpm_optimize, DEFAULT_VOXCPM_OPTIMIZE)
            self.assertEqual(settings.voxcpm_cfg_value, DEFAULT_VOXCPM_CFG_VALUE)
            self.assertEqual(settings.voxcpm_inference_timesteps, DEFAULT_VOXCPM_INFERENCE_TIMESTEPS)
            self.assertEqual(settings.voxcpm_retry_badcase, DEFAULT_VOXCPM_RETRY_BADCASE)
            self.assertEqual(settings.voxcpm_retry_badcase_max_times, DEFAULT_VOXCPM_RETRY_BADCASE_MAX_TIMES)
            self.assertEqual(settings.voxcpm_retry_badcase_ratio_threshold, 20.0)
            self.assertEqual(settings.voxcpm_leading_silence_seconds, DEFAULT_VOXCPM_LEADING_SILENCE_SECONDS)
            self.assertEqual(settings.voxcpm_trailing_silence_seconds, 2.0)
            self.assertEqual(
                settings.voxcpm_stream_prebuffer_max_wait_seconds,
                DEFAULT_VOXCPM_STREAM_PREBUFFER_MAX_WAIT_SECONDS,
            )

    def test_persists_tts_provider_settings(self) -> None:
        payload = settings_to_dict(
            AppSettings(
                tts_provider=TtsProvider.VOXCPM_LOCAL,
                auto_pronounce_on_popup=True,
                auto_pronounce_delay_seconds=0.85,
                pronunciation_content_mode=PronunciationContentMode.WORD,
                voxcpm_endpoint="http://localhost:8810",
                voxcpm_timeout_seconds=22,
                voxcpm_install_root="D:\\Apps\\OhMyWordVox",
                voxcpm_model_cache_root="E:\\Models\\VoxCPM2",
                voxcpm_use_model_mirror=False,
                voxcpm_auto_start=True,
                voxcpm_voice_prompt="A calm English teacher voice.",
                voxcpm_modelscope_namespace="borealis",
                voxcpm_modelscope_repository="oh-my-word-voxcpm2-runtime",
                voxcpm_modelscope_runtime_filename="voxcpm2-runtime-win-x64-cu130-r2.zip",
                voxcpm_modelscope_min_driver_version="581",
                voxcpm_stream_prebuffer_seconds=0.65,
                voxcpm_device=VoxCpmDevice.CPU,
                voxcpm_optimize=True,
                voxcpm_cfg_value=2.1,
                voxcpm_inference_timesteps=16,
                voxcpm_retry_badcase=False,
                voxcpm_retry_badcase_max_times=4,
                voxcpm_retry_badcase_ratio_threshold=3.2,
                voxcpm_leading_silence_seconds=0.18,
                voxcpm_trailing_silence_seconds=0.4,
                voxcpm_stream_prebuffer_max_wait_seconds=1.75,
            )
        )

        self.assertEqual(payload["tts_provider"], "voxcpm_local")
        self.assertTrue(payload["auto_pronounce_on_popup"])
        self.assertEqual(payload["auto_pronounce_delay_seconds"], 0.85)
        self.assertEqual(payload["pronunciation_content_mode"], "word")
        self.assertEqual(payload["voxcpm_endpoint"], "http://localhost:8810")
        self.assertEqual(payload["voxcpm_timeout_seconds"], 22)
        self.assertEqual(payload["voxcpm_install_root"], "D:\\Apps\\OhMyWordVox")
        self.assertEqual(payload["voxcpm_model_cache_root"], "E:\\Models\\VoxCPM2")
        self.assertFalse(payload["voxcpm_use_model_mirror"])
        self.assertTrue(payload["voxcpm_auto_start"])
        self.assertEqual(payload["voxcpm_voice_prompt"], "A calm English teacher voice.")
        self.assertEqual(payload["voxcpm_modelscope_namespace"], "borealis")
        self.assertEqual(payload["voxcpm_modelscope_repository"], "oh-my-word-voxcpm2-runtime")
        self.assertEqual(payload["voxcpm_modelscope_runtime_filename"], "voxcpm2-runtime-win-x64-cu130-r2.zip")
        self.assertEqual(payload["voxcpm_modelscope_min_driver_version"], "581")
        self.assertEqual(payload["voxcpm_stream_prebuffer_seconds"], 0.65)
        self.assertEqual(payload["voxcpm_device"], "cpu")
        self.assertTrue(payload["voxcpm_optimize"])
        self.assertEqual(payload["voxcpm_cfg_value"], 2.1)
        self.assertEqual(payload["voxcpm_inference_timesteps"], 16)
        self.assertFalse(payload["voxcpm_retry_badcase"])
        self.assertEqual(payload["voxcpm_retry_badcase_max_times"], 4)
        self.assertEqual(payload["voxcpm_retry_badcase_ratio_threshold"], 3.2)
        self.assertEqual(payload["voxcpm_leading_silence_seconds"], 0.18)
        self.assertEqual(payload["voxcpm_trailing_silence_seconds"], 0.4)
        self.assertEqual(payload["voxcpm_stream_prebuffer_max_wait_seconds"], 1.75)

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
