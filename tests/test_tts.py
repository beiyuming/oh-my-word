from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PySide6.QtCore import QLocale, QObject, Signal

from app.models import Accent, TtsInitializationState, TtsProvider
from app.tts import (
    PcmStreamBufferDevice,
    PronunciationService,
    StreamingPcmPlayer,
    VoxCpmHttpProvider,
    VoxCpmPlaybackSession,
)


class VoxCpmHttpProviderTests(unittest.TestCase):
    def test_creates_qt_playback_session_with_request_payload(self) -> None:
        captured: dict[str, object] = {}

        class FakeSession(QObject):
            playback_started = Signal(object)
            playback_failed = Signal(object, str)
            finished = Signal(object)

            def __init__(self, **kwargs: object) -> None:
                super().__init__()
                captured.update(kwargs)

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                return None

        wav_player = Mock()
        stream_player = Mock()
        network_manager = Mock()
        with (
            TemporaryDirectory() as tmp_dir,
            patch("app.tts.VoxCpmPlaybackSession", FakeSession),
        ):
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=wav_player,
                stream_player=stream_player,
                network_manager=network_manager,
                stream_prebuffer_seconds=0.6,
                stream_prebuffer_max_wait_seconds=1.4,
            )

            result = provider.speak("focus", accent=Accent.US, request_tag=("req-1", "focus"))

        self.assertTrue(result)
        self.assertEqual(captured["endpoint"], "http://127.0.0.1:8808")
        self.assertEqual(captured["timeout_seconds"], 5)
        self.assertEqual(captured["request_tag"], ("req-1", "focus"))
        self.assertEqual(captured["stream_prebuffer_seconds"], 0.6)
        self.assertEqual(captured["stream_prebuffer_max_wait_seconds"], 1.4)
        self.assertEqual(captured["payload"], {"text": "focus", "accent": "us", "format": "wav"})
        self.assertIs(captured["audio_player"], wav_player)
        self.assertIs(captured["stream_player"], stream_player)
        self.assertIs(captured["network_manager"], network_manager)

    def test_repeated_voxcpm_speech_stops_previous_session_before_replacing_it(self) -> None:
        created: list[QObject] = []

        class FakeSession(QObject):
            playback_started = Signal(object)
            playback_failed = Signal(object, str)
            finished = Signal(object)

            def __init__(self, **_kwargs: object) -> None:
                super().__init__()
                self.stop_calls = 0
                created.append(self)

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                self.stop_calls += 1

        with (
            TemporaryDirectory() as tmp_dir,
            patch("app.tts.VoxCpmPlaybackSession", FakeSession),
        ):
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=Mock(),
                stream_player=Mock(),
                network_manager=Mock(),
            )

            self.assertTrue(provider.speak("focus", accent=Accent.US, request_tag=("req-1", "focus")))
            self.assertTrue(provider.speak("derive", accent=Accent.US, request_tag=("req-2", "derive")))

        self.assertEqual(len(created), 2)
        self.assertEqual(created[0].stop_calls, 1)

    def test_playback_signals_are_forwarded_from_session(self) -> None:
        created: list[QObject] = []

        class FakeSession(QObject):
            playback_started = Signal(object)
            playback_failed = Signal(object, str)
            finished = Signal(object)

            def __init__(self, **_kwargs: object) -> None:
                super().__init__()
                created.append(self)

            def start(self) -> bool:
                return True

            def stop(self) -> None:
                return None

        with (
            TemporaryDirectory() as tmp_dir,
            patch("app.tts.VoxCpmPlaybackSession", FakeSession),
        ):
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=Mock(),
                stream_player=Mock(),
                network_manager=Mock(),
            )
            started = Mock()
            failed = Mock()
            provider.playback_started.connect(started)
            provider.playback_failed.connect(failed)

            self.assertTrue(provider.speak("focus", accent=Accent.US, request_tag=("req-1", "focus")))
            session = created[0]
            session.playback_started.emit(("req-1", "focus"))
            session.playback_failed.emit(("req-1", "focus"), "stream failed")

        started.assert_called_once_with(("req-1", "focus"))
        failed.assert_called_once_with(("req-1", "focus"), "stream failed")
        self.assertEqual(provider.last_error, "stream failed")


class StreamingPcmPlayerTests(unittest.TestCase):
    def test_prebuffers_pcm_before_starting_audio_sink(self) -> None:
        events: list[str] = []

        class FakeAudioFormat:
            class SampleFormat:
                Int16 = object()

            def setSampleRate(self, sample_rate: int) -> None:
                self.sample_rate = sample_rate

            def setChannelCount(self, channels: int) -> None:
                self.channels = channels

            def setSampleFormat(self, sample_format: object) -> None:
                self.sample_format = sample_format

        class FakeDevice:
            def write(self, chunk: bytes) -> int:
                events.append(f"write:{chunk.decode('ascii')}")
                return len(chunk)

        class FakeSink:
            def __init__(self, *_args: object) -> None:
                self.device = FakeDevice()

            def setBufferSize(self, _size: int) -> None:
                return None

            def start(self, device: object) -> None:
                events.append("start")
                self.started_device = device

            def stop(self) -> None:
                return None

        def chunks() -> object:
            for chunk in (b"aa", b"bb", b"cc"):
                events.append(f"yield:{chunk.decode('ascii')}")
                yield chunk

        player = StreamingPcmPlayer(prebuffer_seconds=0.5)
        with (
            patch("app.tts.QAudioFormat", FakeAudioFormat),
            patch("app.tts.QAudioSink", FakeSink),
        ):
            result = player.play_pcm_chunks(
                chunks(),
                sample_rate=4,
                channels=1,
                sample_format="s16le",
            )

        self.assertTrue(result)
        self.assertEqual(events[:3], ["yield:aa", "yield:bb", "start"])
        self.assertEqual(player._device.read(2), b"aa")
        self.assertEqual(player._device.read(2), b"bb")

    def test_pronunciation_service_passes_voxcpm_prebuffer_setting_to_stream_player(self) -> None:
        created: list[float] = []

        class FakeStreamingPcmPlayer:
            def __init__(self, *, prebuffer_seconds: float) -> None:
                created.append(prebuffer_seconds)

        with (
            TemporaryDirectory() as tmp_dir,
            patch("app.tts.StreamingPcmPlayer", FakeStreamingPcmPlayer),
        ):
            service = PronunciationService(
                provider=TtsProvider.VOXCPM_LOCAL,
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                stream_prebuffer_seconds=0.8,
            )

        self.assertEqual(service.provider, TtsProvider.VOXCPM_LOCAL)
        self.assertEqual(created, [0.8])


class VoxCpmPlaybackSessionTests(unittest.TestCase):
    def test_prebuffer_max_wait_deadline_starts_stream_when_pcm_is_available(self) -> None:
        class FakeStreamPlayer:
            last_error = None

            def __init__(self) -> None:
                self.started = False
                self.appended: list[bytes] = []

            def start_stream(self, **_kwargs: object) -> bool:
                self.started = True
                return True

            def append_chunk(self, chunk: bytes) -> None:
                self.appended.append(chunk)

            def stop(self) -> None:
                return None

        player = FakeStreamPlayer()
        session = VoxCpmPlaybackSession(
            network_manager=Mock(),
            endpoint="http://127.0.0.1:8808",
            payload={"text": "focus", "accent": "us", "format": "wav"},
            timeout_seconds=5,
            request_tag=("req-1", "focus"),
            next_audio_path=lambda: Path("unused.wav"),
            audio_player=Mock(),
            stream_player=player,
            stream_prebuffer_seconds=2.0,
            stream_prebuffer_max_wait_seconds=0.25,
        )
        started: list[object] = []
        session.playback_started.connect(lambda tag: started.append(tag))
        session._stream_prebuffer.extend(b"pcm")

        session._on_stream_prebuffer_deadline()

        self.assertTrue(player.started)
        self.assertEqual(player.appended, [b"pcm"])
        self.assertEqual(started, [("req-1", "focus")])

    def test_prebuffer_max_wait_deadline_waits_when_no_pcm_is_available(self) -> None:
        player = Mock()
        session = VoxCpmPlaybackSession(
            network_manager=Mock(),
            endpoint="http://127.0.0.1:8808",
            payload={"text": "focus", "accent": "us", "format": "wav"},
            timeout_seconds=5,
            request_tag=None,
            next_audio_path=lambda: Path("unused.wav"),
            audio_player=Mock(),
            stream_player=player,
            stream_prebuffer_seconds=2.0,
            stream_prebuffer_max_wait_seconds=0.25,
        )

        session._on_stream_prebuffer_deadline()

        player.start_stream.assert_not_called()

    def test_rejects_non_local_endpoint_without_http_request(self) -> None:
        player = Mock()
        provider = VoxCpmHttpProvider(
            endpoint="https://example.com:443",
            timeout_seconds=1,
            cache_dir=Path("."),
            audio_player=player,
        )

        result = provider.speak("focus", accent=Accent.US)

        self.assertFalse(result)
        self.assertIn("local HTTP endpoint", provider.last_error or "")
        player.play.assert_not_called()


class PcmStreamBufferDeviceTests(unittest.TestCase):
    def test_appended_bytes_can_be_read_back_in_pull_order(self) -> None:
        device = PcmStreamBufferDevice()

        device.append_bytes(b"abc")
        device.append_bytes(b"de")

        self.assertEqual(device.read(3), b"abc")
        self.assertEqual(device.read(2), b"de")

    def test_finished_stream_reports_end_after_buffer_drains(self) -> None:
        device = PcmStreamBufferDevice()

        device.append_bytes(b"abc")
        device.mark_finished()

        self.assertFalse(device.atEnd())
        self.assertEqual(device.read(3), b"abc")
        self.assertTrue(device.atEnd())


class PronunciationServiceProviderTests(unittest.TestCase):
    def test_system_qt_starts_not_initialized_until_warm_up(self) -> None:
        with patch("app.tts.QTextToSpeech") as qtts:
            service = PronunciationService(provider=TtsProvider.SYSTEM_QT)

        self.assertIs(service.initialization_state, TtsInitializationState.NOT_INITIALIZED)
        self.assertFalse(service.is_available)
        qtts.assert_not_called()

    def test_system_qt_warm_up_transitions_through_initializing_to_ready(self) -> None:
        backend = Mock()
        voice = Mock()
        voice.locale.return_value = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
        backend.say.return_value = None
        backend.stop.return_value = None

        with patch("app.tts.QTextToSpeech", return_value=backend) as qtts:
            service = PronunciationService(provider=TtsProvider.SYSTEM_QT, accent=Accent.US)
            self.assertIs(service.initialization_state, TtsInitializationState.NOT_INITIALIZED)

            def available_voices() -> list[Mock]:
                self.assertIs(service.initialization_state, TtsInitializationState.INITIALIZING)
                return [voice]

            backend.availableVoices.side_effect = available_voices
            state = service.warm_up()
            second_state = service.warm_up()

        self.assertIs(state, TtsInitializationState.READY)
        self.assertIs(second_state, TtsInitializationState.READY)
        self.assertTrue(service.is_available)
        self.assertIs(service.initialization_state, TtsInitializationState.READY)
        self.assertEqual(qtts.call_count, 1)
        backend.setVoice.assert_called_once()

    def test_system_qt_warm_up_failure_sets_unavailable(self) -> None:
        backend = Mock()
        backend.availableVoices.return_value = []

        with patch("app.tts.QTextToSpeech", return_value=backend):
            service = PronunciationService(provider=TtsProvider.SYSTEM_QT)
            state = service.warm_up()

        self.assertIs(state, TtsInitializationState.UNAVAILABLE)
        self.assertIs(service.initialization_state, TtsInitializationState.UNAVAILABLE)
        self.assertFalse(service.is_available)
        self.assertIn("No text-to-speech voices", service.last_error or "")
        self.assertFalse(service.speak("focus"))

    def test_ready_system_qt_speak_uses_backend_after_warm_up(self) -> None:
        backend = Mock()
        voice = Mock()
        voice.locale.return_value = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
        backend.availableVoices.side_effect = lambda: [voice]
        backend.say.return_value = None

        with patch("app.tts.QTextToSpeech", return_value=backend):
            service = PronunciationService(provider=TtsProvider.SYSTEM_QT, accent=Accent.US)
            service.warm_up()
            result = service.speak("focus. Focus on review.")

        self.assertTrue(result)
        backend.say.assert_called_once_with("focus. Focus on review.")

    def test_uses_voxcpm_provider_when_selected(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            service = PronunciationService(
                provider=TtsProvider.VOXCPM_LOCAL,
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
            )

        self.assertEqual(service.provider, TtsProvider.VOXCPM_LOCAL)
        self.assertIs(service.initialization_state, TtsInitializationState.READY)
        self.assertIs(service.warm_up(), TtsInitializationState.READY)

    def test_voxcpm_provider_accepts_request_tag_argument(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            service = PronunciationService(
                provider=TtsProvider.VOXCPM_LOCAL,
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
            )

        with patch.object(service._backend, "speak", return_value=True) as speak:
            result = service.speak("focus", accent=Accent.US, request_tag=("req-1", "focus"))

        self.assertTrue(result)
        speak.assert_called_once_with("focus", accent=Accent.US, request_tag=("req-1", "focus"))
