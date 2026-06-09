from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QLocale, QUrl, Signal

from .models import (
    DEFAULT_VOXCPM_ENDPOINT,
    DEFAULT_VOXCPM_TIMEOUT_SECONDS,
    TtsProvider,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except ImportError:  # pragma: no cover - depends on optional Qt module
    QAudioOutput = None  # type: ignore[assignment]
    QMediaPlayer = None  # type: ignore[assignment]

try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except ImportError:  # pragma: no cover - depends on optional Qt module
    QTextToSpeech = None  # type: ignore[assignment]


class QtTextToSpeechProvider:
    """Best-effort QtTextToSpeech backend with English voice preference selection."""

    def __init__(self, owner: QObject, accent: Any | None = None) -> None:
        self._owner = owner
        self._configured_accent = accent
        self._backend: QTextToSpeech | None = None
        self._available = False
        self._last_error: str | None = None
        self._initialize_backend()

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def set_accent(self, accent: Any | None) -> None:
        self._configured_accent = accent
        self._apply_voice_preference()

    def speak(self, text: str, *, accent: Any | None = None) -> bool:
        message = text.strip()
        if not message:
            return False
        if not self._available or self._backend is None:
            self._report_error("Offline pronunciation is unavailable.")
            return False

        if accent is not None:
            self.set_accent(accent)
            if not self._available:
                return False

        try:
            self._backend.say(message)
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._report_error(f"Text-to-speech failed: {exc}")
            return False
        return True

    def stop(self) -> None:
        if self._backend is None:
            return
        try:
            self._backend.stop()
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._report_error(f"Stopping text-to-speech failed: {exc}")

    def _initialize_backend(self) -> None:
        if QTextToSpeech is None:
            self._report_error("PySide6 QtTextToSpeech is not installed.")
            return

        try:
            self._backend = QTextToSpeech(self._owner)
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._report_error(f"Qt text-to-speech backend failed to initialize: {exc}")
            return

        self._apply_voice_preference()

    def _apply_voice_preference(self) -> None:
        if self._backend is None:
            return

        try:
            voices = list(self._backend.availableVoices())
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._report_error(f"Could not enumerate text-to-speech voices: {exc}")
            return

        if not voices:
            self._report_error("No text-to-speech voices are available.")
            return

        preferred_voice = self._select_voice(voices, self._configured_accent)
        if preferred_voice is not None:
            try:
                self._backend.setVoice(preferred_voice)
            except Exception as exc:  # pragma: no cover - backend-specific failure
                self._report_error(f"Could not select text-to-speech voice: {exc}")
                return

        self._available = True
        self._last_error = None

    def _select_voice(self, voices: list[Any], accent: Any | None) -> Any | None:
        target_name = str(getattr(accent, "value", accent) or "").strip().lower()

        locale_candidates = []
        if target_name in {"uk", "gb", "en-gb"}:
            locale_candidates.append(QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom))
        elif target_name in {"us", "en-us"}:
            locale_candidates.append(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))

        locale_candidates.extend(
            [
                QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom),
                QLocale(QLocale.Language.English, QLocale.Country.UnitedStates),
                QLocale(QLocale.Language.English),
            ]
        )

        for locale in locale_candidates:
            voice = self._first_voice_for_locale(voices, locale)
            if voice is not None:
                return voice

        for voice in voices:
            voice_locale = voice.locale()
            if voice_locale.language() == QLocale.Language.English:
                return voice

        return voices[0]

    @staticmethod
    def _first_voice_for_locale(voices: list[Any], locale: QLocale) -> Any | None:
        for voice in voices:
            voice_locale = voice.locale()
            if voice_locale.language() != locale.language():
                continue
            if locale.territory() and voice_locale.territory() != locale.territory():
                continue
            return voice
        return None

    def _report_error(self, message: str) -> None:
        self._last_error = message
        self._available = False


class LocalWavPlayer(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._last_error: str | None = None
        self._audio_output: QAudioOutput | None = None
        self._player: QMediaPlayer | None = None
        if QMediaPlayer is not None and QAudioOutput is not None:
            self._audio_output = QAudioOutput(self)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._audio_output)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def play(self, path: Path) -> bool:
        if self._player is None:
            self._last_error = "QtMultimedia audio playback is unavailable."
            return False
        try:
            self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
            self._player.play()
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._last_error = f"Playing synthesized audio failed: {exc}"
            return False
        self._last_error = None
        return True

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()


class VoxCpmHttpProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: int,
        cache_dir: Path,
        audio_player: LocalWavPlayer | Any | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._cache_dir = cache_dir
        self._audio_player = audio_player or LocalWavPlayer()
        self._last_error: str | None = None
        self._available = _is_local_http_endpoint(self._endpoint)
        if not self._available:
            self._last_error = "VoxCPM endpoint must be a local HTTP endpoint."

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def set_accent(self, accent: Any | None) -> None:
        return None

    def speak(self, text: str, *, accent: Any | None = None) -> bool:
        message = text.strip()
        if not message:
            return False
        if not self._available:
            self._last_error = "VoxCPM endpoint must be a local HTTP endpoint."
            return False

        payload = {
            "text": message,
            "accent": str(getattr(accent, "value", accent) or "").lower(),
            "format": "wav",
        }
        request = Request(
            f"{self._endpoint}/synthesize",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                audio_bytes = response.read()
        except Exception as exc:
            self._last_error = f"VoxCPM local service request failed: {exc}"
            return False

        if not audio_bytes:
            self._last_error = "VoxCPM local service returned an empty audio response."
            return False

        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            audio_path = self._cache_dir / "voxcpm-current.wav"
            audio_path.write_bytes(audio_bytes)
            if not self._audio_player.play(audio_path):
                player_error = getattr(self._audio_player, "last_error", None)
                self._last_error = player_error or "Playing VoxCPM audio failed."
                return False
        except Exception as exc:
            self._last_error = f"Playing VoxCPM audio failed: {exc}"
            return False

        self._last_error = None
        return True

    def stop(self) -> None:
        self._audio_player.stop()


class PronunciationService(QObject):
    availability_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        accent: Any | None = None,
        provider: TtsProvider = TtsProvider.SYSTEM_QT,
        endpoint: str = DEFAULT_VOXCPM_ENDPOINT,
        timeout_seconds: int = DEFAULT_VOXCPM_TIMEOUT_SECONDS,
        cache_dir: Path | None = None,
        on_error: Callable[[str], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._provider_name = provider
        self._backend: QtTextToSpeechProvider | VoxCpmHttpProvider
        self._backend = self._create_backend(
            accent=accent,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            cache_dir=cache_dir,
        )

        if on_error is not None:
            self.error_occurred.connect(on_error)

        self.availability_changed.emit(self.is_available)

    @property
    def provider(self) -> TtsProvider:
        return self._provider_name

    @property
    def is_available(self) -> bool:
        return self._backend.is_available

    @property
    def last_error(self) -> str | None:
        return self._backend.last_error

    def set_accent(self, accent: Any | None) -> None:
        was_available = self.is_available
        self._backend.set_accent(accent)
        if self.is_available != was_available:
            self.availability_changed.emit(self.is_available)

    def speak(self, text: str, *, accent: Any | None = None) -> bool:
        result = self._backend.speak(text, accent=accent)
        if not result and self.last_error:
            self.error_occurred.emit(self.last_error)
            self.availability_changed.emit(self.is_available)
        return result

    def stop(self) -> None:
        self._backend.stop()

    def _create_backend(
        self,
        *,
        accent: Any | None,
        endpoint: str,
        timeout_seconds: int,
        cache_dir: Path | None,
    ) -> QtTextToSpeechProvider | VoxCpmHttpProvider:
        if self._provider_name is TtsProvider.VOXCPM_LOCAL:
            return VoxCpmHttpProvider(
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                cache_dir=cache_dir or Path.cwd() / "storage" / "tts_cache",
            )
        return QtTextToSpeechProvider(self, accent=accent)


def _is_local_http_endpoint(value: str) -> bool:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "http" and parsed.port is not None and hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
