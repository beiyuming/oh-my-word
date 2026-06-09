from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from app.models import Accent, TtsProvider
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


class VoxCpmHttpProviderTests(unittest.TestCase):
    def test_posts_text_and_plays_wav_bytes(self) -> None:
        player = Mock()
        with TemporaryDirectory() as tmp_dir:
            provider = VoxCpmHttpProvider(
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
                audio_player=player,
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


class PronunciationServiceProviderTests(unittest.TestCase):
    def test_uses_voxcpm_provider_when_selected(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            service = PronunciationService(
                provider=TtsProvider.VOXCPM_LOCAL,
                endpoint="http://127.0.0.1:8808",
                timeout_seconds=5,
                cache_dir=Path(tmp_dir),
            )

        self.assertEqual(service.provider, TtsProvider.VOXCPM_LOCAL)
