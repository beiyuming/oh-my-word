from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PySide6.QtCore import QLocale

from app.models import Accent, TtsInitializationState, TtsProvider
from app.tts import PronunciationService, VoxCpmHttpProvider


class _FakeResponse:
    status = 200

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class _FakeStreamingResponse:
    status = 200

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.headers = {
            "X-OhMyWord-Sample-Rate": "48000",
            "X-OhMyWord-Channels": "1",
            "X-OhMyWord-Sample-Format": "s16le",
        }
        self.read_count = 0

    def __enter__(self) -> "_FakeStreamingResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        _ = size
        self.read_count += 1
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class VoxCpmHttpProviderTests(unittest.TestCase):
    def test_streams_pcm_chunks_without_waiting_for_full_wav_response(self) -> None:
        wav_player = Mock()
        stream_player = Mock()
        response = _FakeStreamingResponse([b"first", b"second"])

        def play_first_chunk(chunks: object, **kwargs: object) -> bool:
            chunk_iter = iter(chunks)  # type: ignore[arg-type]
            self.assertEqual(next(chunk_iter), b"first")
            self.assertEqual(kwargs["sample_rate"], 48000)
            self.assertEqual(kwargs["channels"], 1)
            self.assertEqual(kwargs["sample_format"], "s16le")
            return True

        stream_player.play_pcm_chunks.side_effect = play_first_chunk
        with TemporaryDirectory() as tmp_dir:
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=wav_player,
                stream_player=stream_player,
            )

            with patch("app.tts.urlopen", return_value=response) as urlopen:
                result = provider.speak("focus", accent=Accent.US)

        self.assertTrue(result)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8808/synthesize_stream")
        self.assertEqual(response.read_count, 1)
        wav_player.play.assert_not_called()
        stream_player.play_pcm_chunks.assert_called_once()

    def test_posts_text_and_plays_wav_bytes(self) -> None:
        player = Mock()
        with TemporaryDirectory() as tmp_dir:
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=player,
                stream_player=None,
            )

            with patch("app.tts.urlopen", return_value=_FakeResponse(b"RIFFfake-wave")) as urlopen:
                result = provider.speak("focus. Focus on review.", accent=Accent.US)

        self.assertTrue(result)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8808/synthesize")
        self.assertEqual(request.get_method(), "POST")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["text"], "focus. Focus on review.")
        self.assertEqual(payload["accent"], "us")
        player.play.assert_called_once()

    def test_repeated_voxcpm_speech_uses_rotating_cache_files_and_stops_previous_audio(self) -> None:
        player = Mock()
        with TemporaryDirectory() as tmp_dir:
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=player,
                stream_player=None,
            )

            with patch("app.tts.urlopen", return_value=_FakeResponse(b"RIFFfake-wave")):
                self.assertTrue(provider.speak("focus", accent=Accent.US))
                self.assertTrue(provider.speak("derive", accent=Accent.US))

        first_path = player.play.call_args_list[0].args[0]
        second_path = player.play.call_args_list[1].args[0]
        self.assertNotEqual(first_path, second_path)
        self.assertEqual(player.stop.call_count, 2)

    def test_returns_false_when_http_fails(self) -> None:
        player = Mock()
        provider = VoxCpmHttpProvider(
            endpoint="http://127.0.0.1:8808",
            timeout_seconds=1,
            cache_dir=Path("."),
            audio_player=player,
        )

        with patch("app.tts.urlopen", side_effect=OSError("service down")):
            result = provider.speak("focus", accent=Accent.US)

        self.assertFalse(result)
        self.assertIn("service down", provider.last_error or "")
        player.play.assert_not_called()

    def test_rejects_non_local_endpoint_without_http_request(self) -> None:
        player = Mock()
        provider = VoxCpmHttpProvider(
            endpoint="https://example.com:443",
            timeout_seconds=1,
            cache_dir=Path("."),
            audio_player=player,
        )

        with patch("app.tts.urlopen") as urlopen:
            result = provider.speak("focus", accent=Accent.US)

        self.assertFalse(result)
        self.assertIn("local HTTP endpoint", provider.last_error or "")
        urlopen.assert_not_called()
        player.play.assert_not_called()


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
