from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from time import sleep
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QCoreApplication, QObject, QLocale, QUrl, Signal

from .models import (
    DEFAULT_VOXCPM_ENDPOINT,
    DEFAULT_VOXCPM_STREAM_PREBUFFER_SECONDS,
    DEFAULT_VOXCPM_TIMEOUT_SECONDS,
    TtsInitializationState,
    TtsProvider,
)

try:
    from PySide6.QtMultimedia import QAudioFormat, QAudioOutput, QAudioSink, QMediaPlayer
except ImportError:  # pragma: no cover - depends on optional Qt module
    QAudioFormat = None  # type: ignore[assignment]
    QAudioOutput = None  # type: ignore[assignment]
    QAudioSink = None  # type: ignore[assignment]
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
        self._initialization_state = TtsInitializationState.NOT_INITIALIZED

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def initialization_state(self) -> TtsInitializationState:
        return self._initialization_state

    def warm_up(self) -> TtsInitializationState:
        if self._initialization_state in {
            TtsInitializationState.READY,
            TtsInitializationState.UNAVAILABLE,
            TtsInitializationState.INITIALIZING,
        }:
            return self._initialization_state

        self._initialization_state = TtsInitializationState.INITIALIZING
        self._initialize_backend()
        return self._initialization_state

    def set_accent(self, accent: Any | None) -> None:
        self._configured_accent = accent
        self._apply_voice_preference()

    def speak(self, text: str, *, accent: Any | None = None) -> bool:
        message = text.strip()
        if not message:
            return False
        if self._initialization_state is not TtsInitializationState.READY or self._backend is None:
            return False

        if accent is not None:
            self.set_accent(accent)
            if self._initialization_state is not TtsInitializationState.READY:
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
        self._initialization_state = TtsInitializationState.READY

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
        self._initialization_state = TtsInitializationState.UNAVAILABLE


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
            self._player.stop()
            self._player.setSource(QUrl())
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


class StreamingPcmPlayer(QObject):
    def __init__(
        self,
        parent: QObject | None = None,
        *,
        prebuffer_seconds: float = DEFAULT_VOXCPM_STREAM_PREBUFFER_SECONDS,
    ) -> None:
        super().__init__(parent)
        self._last_error: str | None = None
        self._sink: Any | None = None
        self._device: Any | None = None
        self._prebuffer_seconds = min(max(float(prebuffer_seconds), 0.0), 2.0)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def play_pcm_chunks(
        self,
        chunks: Iterable[bytes],
        *,
        sample_rate: int,
        channels: int,
        sample_format: str,
    ) -> bool:
        if QAudioSink is None or QAudioFormat is None:
            self._last_error = "QtMultimedia streaming audio playback is unavailable."
            return False
        if sample_format != "s16le":
            self._last_error = f"Unsupported streaming PCM format: {sample_format}"
            return False
        if sample_rate <= 0 or channels <= 0:
            self._last_error = "Invalid streaming PCM audio format."
            return False

        try:
            self.stop()
            chunk_iter = iter(chunks)
            prebuffered_chunks = self._prebuffer_chunks(
                chunk_iter,
                sample_rate=sample_rate,
                channels=channels,
            )
            if not prebuffered_chunks:
                self._last_error = "VoxCPM local service returned an empty audio stream."
                return False

            audio_format = QAudioFormat()
            audio_format.setSampleRate(sample_rate)
            audio_format.setChannelCount(channels)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._sink = QAudioSink(audio_format, self)
            self._sink.setBufferSize(max(32768, sample_rate * channels * 2))
            self._device = self._sink.start()
            if self._device is None:
                self._last_error = "Could not start streaming audio output."
                return False

            for chunk in prebuffered_chunks:
                if not self._write_chunk(chunk):
                    return False

            for chunk in chunk_iter:
                if not chunk:
                    continue
                if not self._write_chunk(chunk):
                    return False
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._last_error = f"Streaming VoxCPM audio failed: {exc}"
            return False

        self._last_error = None
        return True

    def stop(self) -> None:
        if self._sink is not None:
            self._sink.stop()
        self._sink = None
        self._device = None

    def _write_chunk(self, chunk: bytes) -> bool:
        assert self._device is not None
        offset = 0
        stalled_ticks = 0
        while offset < len(chunk):
            written = self._device.write(chunk[offset:])
            if written < 0:
                self._last_error = "Streaming audio output rejected PCM data."
                return False
            if written == 0:
                stalled_ticks += 1
                if stalled_ticks > 1000:
                    self._last_error = "Streaming audio output stalled."
                    return False
                app = QCoreApplication.instance()
                if app is not None:
                    app.processEvents()
                sleep(0.005)
                continue
            offset += written
            stalled_ticks = 0
        return True

    def _prebuffer_chunks(
        self,
        chunks: Iterable[bytes],
        *,
        sample_rate: int,
        channels: int,
    ) -> list[bytes]:
        target_bytes = int(sample_rate * channels * 2 * self._prebuffer_seconds)
        buffered: list[bytes] = []
        buffered_bytes = 0
        for chunk in chunks:
            if not chunk:
                continue
            buffered.append(chunk)
            buffered_bytes += len(chunk)
            if buffered_bytes >= target_bytes:
                break
        return buffered


_DEFAULT_STREAM_PLAYER = object()
_PCM_STREAM_READ_SIZE = 32768


class VoxCpmHttpProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: int,
        cache_dir: Path,
        audio_player: LocalWavPlayer | Any | None = None,
        stream_player: Any = _DEFAULT_STREAM_PLAYER,
        stream_prebuffer_seconds: float = DEFAULT_VOXCPM_STREAM_PREBUFFER_SECONDS,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._cache_dir = cache_dir
        self._audio_player = audio_player or LocalWavPlayer()
        self._stream_player = (
            StreamingPcmPlayer(prebuffer_seconds=stream_prebuffer_seconds)
            if stream_player is _DEFAULT_STREAM_PLAYER
            else stream_player
        )
        self._last_error: str | None = None
        self._cache_counter = 0
        self._available = _is_local_http_endpoint(self._endpoint)
        self._initialization_state = (
            TtsInitializationState.READY if self._available else TtsInitializationState.UNAVAILABLE
        )
        if not self._available:
            self._last_error = "VoxCPM endpoint must be a local HTTP endpoint."

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def initialization_state(self) -> TtsInitializationState:
        return self._initialization_state

    def set_accent(self, accent: Any | None) -> None:
        return None

    def warm_up(self) -> TtsInitializationState:
        return self._initialization_state

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

        if self._stream_player is not None:
            streaming_result = self._speak_streaming(payload)
            if streaming_result is not None:
                return streaming_result

        return self._speak_wav(payload)

    def _speak_streaming(self, payload: dict[str, str]) -> bool | None:
        request = Request(
            f"{self._endpoint}/synthesize_stream",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                sample_rate = _positive_header_int(response, "X-OhMyWord-Sample-Rate", 48000)
                channels = _positive_header_int(response, "X-OhMyWord-Channels", 1)
                sample_format = _header_text(response, "X-OhMyWord-Sample-Format", "s16le")

                def chunks() -> Iterable[bytes]:
                    while True:
                        chunk = response.read(_PCM_STREAM_READ_SIZE)
                        if not chunk:
                            break
                        yield chunk

                if not self._stream_player.play_pcm_chunks(
                    chunks(),
                    sample_rate=sample_rate,
                    channels=channels,
                    sample_format=sample_format,
                ):
                    player_error = getattr(self._stream_player, "last_error", None)
                    self._last_error = player_error or "Streaming VoxCPM audio failed."
                    return False
        except HTTPError as exc:
            if exc.code in {404, 405}:
                return None
            self._last_error = f"VoxCPM local streaming request failed: {exc}"
            return False
        except Exception as exc:
            self._last_error = f"VoxCPM local streaming request failed: {exc}"
            return False

        self._last_error = None
        return True

    def _speak_wav(self, payload: dict[str, str]) -> bool:
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
            self._audio_player.stop()
            audio_path = self._next_audio_path()
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
        if self._stream_player is not None:
            self._stream_player.stop()

    def _next_audio_path(self) -> Path:
        path = self._cache_dir / f"voxcpm-{self._cache_counter % 4}.wav"
        self._cache_counter += 1
        return path


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
        stream_prebuffer_seconds: float = DEFAULT_VOXCPM_STREAM_PREBUFFER_SECONDS,
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
            stream_prebuffer_seconds=stream_prebuffer_seconds,
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

    @property
    def initialization_state(self) -> TtsInitializationState:
        return self._backend.initialization_state

    def warm_up(self) -> TtsInitializationState:
        was_available = self.is_available
        state = self._backend.warm_up()
        if self.last_error and state is TtsInitializationState.UNAVAILABLE:
            self.error_occurred.emit(self.last_error)
        if self.is_available != was_available:
            self.availability_changed.emit(self.is_available)
        return state

    def set_accent(self, accent: Any | None) -> None:
        was_available = self.is_available
        self._backend.set_accent(accent)
        if self.is_available != was_available:
            self.availability_changed.emit(self.is_available)

    def speak(self, text: str, *, accent: Any | None = None) -> bool:
        if self.initialization_state is not TtsInitializationState.READY:
            return False
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
        stream_prebuffer_seconds: float,
    ) -> QtTextToSpeechProvider | VoxCpmHttpProvider:
        if self._provider_name is TtsProvider.VOXCPM_LOCAL:
            return VoxCpmHttpProvider(
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                cache_dir=cache_dir or Path.cwd() / "storage" / "tts_cache",
                stream_prebuffer_seconds=stream_prebuffer_seconds,
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


def _header_text(response: Any, name: str, default: str) -> str:
    headers = getattr(response, "headers", {})
    value = headers.get(name, default) if hasattr(headers, "get") else default
    return str(value or default).strip() or default


def _positive_header_int(response: Any, name: str, default: int) -> int:
    try:
        value = int(_header_text(response, name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default
