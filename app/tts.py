from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import QIODevice, QLocale, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .models import (
    DEFAULT_VOXCPM_ENDPOINT,
    DEFAULT_VOXCPM_STREAM_PREBUFFER_MAX_WAIT_SECONDS,
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


_LOGGER = logging.getLogger("oh_my_word.tts")


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

    def speak(self, text: str, *, accent: Any | None = None, request_tag: object | None = None) -> bool:
        _ = request_tag
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


class PcmStreamBufferDevice(QIODevice):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._buffer = bytearray()
        self._finished = False
        self.open(QIODevice.OpenModeFlag.ReadOnly)

    def append_bytes(self, data: bytes) -> None:
        if not data:
            return
        self._buffer.extend(data)
        self.readyRead.emit()

    def mark_finished(self) -> None:
        self._finished = True
        self.readyRead.emit()
        self.readChannelFinished.emit()

    def reset_stream(self) -> None:
        self._buffer.clear()
        self._finished = False

    def bytesAvailable(self) -> int:  # type: ignore[override]
        return len(self._buffer) + super().bytesAvailable()

    def atEnd(self) -> bool:  # type: ignore[override]
        return self._finished and not self._buffer

    def isSequential(self) -> bool:  # type: ignore[override]
        return True

    def readData(self, maxlen: int) -> bytes:  # type: ignore[override]
        if maxlen <= 0 or not self._buffer:
            return b""
        data = bytes(self._buffer[:maxlen])
        del self._buffer[:maxlen]
        return data

    def writeData(self, data: bytes) -> int:  # type: ignore[override]
        _ = data
        return -1


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
        self._device: PcmStreamBufferDevice | None = None
        self._prebuffer_seconds = min(max(float(prebuffer_seconds), 0.0), 2.0)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def start_stream(self, *, sample_rate: int, channels: int, sample_format: str) -> bool:
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
            audio_format = QAudioFormat()
            audio_format.setSampleRate(sample_rate)
            audio_format.setChannelCount(channels)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._device = PcmStreamBufferDevice(self)
            self._sink = QAudioSink(audio_format, self)
            self._sink.setBufferSize(max(32768, sample_rate * channels * 2))
            self._sink.start(self._device)
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._last_error = f"Streaming VoxCPM audio failed: {exc}"
            return False

        self._last_error = None
        return True

    def append_chunk(self, chunk: bytes) -> None:
        if self._device is not None:
            self._device.append_bytes(chunk)

    def finish_stream(self) -> None:
        if self._device is not None:
            self._device.mark_finished()

    def play_pcm_chunks(
        self,
        chunks: Iterable[bytes],
        *,
        sample_rate: int,
        channels: int,
        sample_format: str,
    ) -> bool:
        chunk_iter = iter(chunks)
        prebuffered_chunks = self._prebuffer_chunks(
            chunk_iter,
            sample_rate=sample_rate,
            channels=channels,
        )
        if not prebuffered_chunks:
            self._last_error = "VoxCPM local service returned an empty audio stream."
            return False
        if not self.start_stream(sample_rate=sample_rate, channels=channels, sample_format=sample_format):
            return False
        for chunk in prebuffered_chunks:
            self.append_chunk(chunk)
        for chunk in chunk_iter:
            if chunk:
                self.append_chunk(chunk)
        self.finish_stream()
        return True

    def stop(self) -> None:
        if self._sink is not None:
            self._sink.stop()
        self._sink = None
        if self._device is not None:
            self._device.close()
        self._device = None

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


class VoxCpmPlaybackSession(QObject):
    playback_started = Signal(object)
    playback_failed = Signal(object, str)
    finished = Signal(object)

    def __init__(
        self,
        *,
        network_manager: QNetworkAccessManager,
        endpoint: str,
        payload: dict[str, str],
        timeout_seconds: int,
        request_tag: object | None,
        next_audio_path: Callable[[], Path],
        audio_player: LocalWavPlayer,
        stream_player: StreamingPcmPlayer | None,
        stream_prebuffer_seconds: float,
        stream_prebuffer_max_wait_seconds: float,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._network_manager = network_manager
        self._endpoint = endpoint.rstrip("/")
        self._payload = payload
        self._timeout_seconds = timeout_seconds
        self._request_tag = request_tag
        self._next_audio_path = next_audio_path
        self._audio_player = audio_player
        self._stream_player = stream_player
        self._stream_prebuffer_seconds = min(max(float(stream_prebuffer_seconds), 0.0), 2.0)
        self._stream_prebuffer_max_wait_seconds = min(
            max(float(stream_prebuffer_max_wait_seconds), 0.1),
            30.0,
        )
        self._stream_reply: QNetworkReply | None = None
        self._wav_reply: QNetworkReply | None = None
        self._stopped = False
        self._stream_started = False
        self._stream_sample_rate = 48000
        self._stream_channels = 1
        self._stream_sample_format = "s16le"
        self._stream_prebuffer = bytearray()
        self._stream_request_started_at = 0.0
        self._stream_first_byte_at: float | None = None
        self._stream_prebuffer_reached_at: float | None = None
        self._stream_audio_bytes = 0
        self._stream_prebuffer_deadline_reached = False
        self._stream_prebuffer_timer = QTimer(self)
        self._stream_prebuffer_timer.setSingleShot(True)
        self._stream_prebuffer_timer.timeout.connect(self._on_stream_prebuffer_deadline)

    def start(self) -> bool:
        if self._stream_player is None:
            self._start_wav_request()
            return True
        self._start_stream_request()
        return True

    def stop(self) -> None:
        self._stopped = True
        self._stream_prebuffer_timer.stop()
        self._abort_reply(self._stream_reply)
        self._stream_reply = None
        self._abort_reply(self._wav_reply)
        self._wav_reply = None
        self._audio_player.stop()
        if self._stream_player is not None:
            self._stream_player.stop()

    def _start_stream_request(self) -> None:
        request = self._json_request(f"{self._endpoint}/synthesize_stream")
        self._stream_request_started_at = time.perf_counter()
        self._stream_prebuffer_timer.start(int(self._stream_prebuffer_max_wait_seconds * 1000))
        self._stream_reply = self._network_manager.post(request, json.dumps(self._payload).encode("utf-8"))
        self._stream_reply.metaDataChanged.connect(self._on_stream_metadata_changed)
        self._stream_reply.readyRead.connect(self._on_stream_ready_read)
        self._stream_reply.finished.connect(self._on_stream_finished)

    def _on_stream_metadata_changed(self) -> None:
        if self._stream_reply is None:
            return
        self._stream_sample_rate = _reply_positive_int(
            self._stream_reply,
            b"X-OhMyWord-Sample-Rate",
            48000,
        )
        self._stream_channels = _reply_positive_int(
            self._stream_reply,
            b"X-OhMyWord-Channels",
            1,
        )
        self._stream_sample_format = _reply_header_text(
            self._stream_reply,
            b"X-OhMyWord-Sample-Format",
            "s16le",
        )

    def _on_stream_ready_read(self) -> None:
        if self._stopped or self._stream_reply is None:
            return
        self._on_stream_metadata_changed()
        data = bytes(self._stream_reply.readAll())
        if not data:
            return
        self._record_stream_bytes(len(data))
        if self._stream_started:
            assert self._stream_player is not None
            self._stream_player.append_chunk(data)
            return
        self._stream_prebuffer.extend(data)
        if self._stream_prebuffer_deadline_reached or len(self._stream_prebuffer) >= self._target_prebuffer_bytes():
            self._start_stream_player()

    def _on_stream_finished(self) -> None:
        reply = self._stream_reply
        self._stream_reply = None
        if reply is None:
            return

        if self._stopped:
            reply.deleteLater()
            return

        self._on_stream_metadata_changed()
        trailing = bytes(reply.readAll())
        if trailing:
            self._record_stream_bytes(len(trailing))
            if self._stream_started and self._stream_player is not None:
                self._stream_player.append_chunk(trailing)
            else:
                self._stream_prebuffer.extend(trailing)

        status_code = _reply_status_code(reply)
        network_error = reply.error()
        reply.deleteLater()

        if status_code in {404, 405}:
            self._stream_prebuffer_timer.stop()
            _LOGGER.warning(
                "VoxCPM local service does not support /synthesize_stream (HTTP %s); falling back to full WAV /synthesize.",
                status_code,
            )
            self._start_wav_request()
            return

        if network_error != QNetworkReply.NetworkError.NoError:
            self._stream_prebuffer_timer.stop()
            self._fail(f"VoxCPM local streaming request failed: {reply.errorString()}")
            return

        if not self._stream_started:
            if not self._stream_prebuffer:
                self._fail("VoxCPM local service returned an empty audio stream.")
                return
            if not self._start_stream_player():
                return

        if self._stream_player is not None:
            self._stream_player.finish_stream()
        self._stream_prebuffer_timer.stop()
        self._log_stream_generation_finished()
        self._complete()

    def _on_stream_prebuffer_deadline(self) -> None:
        if self._stopped or self._stream_started:
            return
        self._stream_prebuffer_deadline_reached = True
        if self._stream_prebuffer:
            self._start_stream_player()

    def _start_stream_player(self) -> bool:
        if self._stream_started:
            return True
        if self._stream_player is None:
            self._fail("QtMultimedia streaming audio playback is unavailable.")
            return False
        if not self._stream_player.start_stream(
            sample_rate=self._stream_sample_rate,
            channels=self._stream_channels,
            sample_format=self._stream_sample_format,
        ):
            self._fail(self._stream_player.last_error or "Streaming VoxCPM audio failed.")
            return False
        if self._stream_prebuffer:
            self._stream_player.append_chunk(bytes(self._stream_prebuffer))
            self._stream_prebuffer.clear()
        self._stream_started = True
        self._stream_prebuffer_reached_at = time.perf_counter()
        _LOGGER.info(
            "VoxCPM stream prebuffer reached in %.3fs; buffered_audio_seconds=%.3f target_audio_seconds=%.3f max_wait_seconds=%.3f deadline_reached=%s",
            self._elapsed_since_request(self._stream_prebuffer_reached_at),
            self._stream_audio_seconds(),
            self._stream_prebuffer_seconds,
            self._stream_prebuffer_max_wait_seconds,
            self._stream_prebuffer_deadline_reached,
        )
        self.playback_started.emit(self._request_tag)
        return True

    def _start_wav_request(self) -> None:
        request = self._json_request(f"{self._endpoint}/synthesize")
        self._wav_reply = self._network_manager.post(request, json.dumps(self._payload).encode("utf-8"))
        self._wav_reply.finished.connect(self._on_wav_finished)

    def _on_wav_finished(self) -> None:
        reply = self._wav_reply
        self._wav_reply = None
        if reply is None:
            return

        if self._stopped:
            reply.deleteLater()
            return

        audio_bytes = bytes(reply.readAll())
        network_error = reply.error()
        error_text = reply.errorString()
        reply.deleteLater()

        if network_error != QNetworkReply.NetworkError.NoError:
            self._fail(f"VoxCPM local service request failed: {error_text}")
            return
        if not audio_bytes:
            self._fail("VoxCPM local service returned an empty audio response.")
            return

        try:
            audio_path = self._next_audio_path()
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            self._audio_player.stop()
            audio_path.write_bytes(audio_bytes)
            if not self._audio_player.play(audio_path):
                self._fail(self._audio_player.last_error or "Playing VoxCPM audio failed.")
                return
        except Exception as exc:
            self._fail(f"Playing VoxCPM audio failed: {exc}")
            return

        self.playback_started.emit(self._request_tag)
        self._complete()

    def _target_prebuffer_bytes(self) -> int:
        return int(self._stream_sample_rate * self._stream_channels * 2 * self._stream_prebuffer_seconds)

    def _record_stream_bytes(self, byte_count: int) -> None:
        if self._stream_first_byte_at is None:
            self._stream_first_byte_at = time.perf_counter()
            _LOGGER.info(
                "VoxCPM stream first byte in %.3fs.",
                self._elapsed_since_request(self._stream_first_byte_at),
            )
        self._stream_audio_bytes += byte_count

    def _stream_audio_seconds(self) -> float:
        bytes_per_second = self._stream_sample_rate * self._stream_channels * 2
        if bytes_per_second <= 0:
            return 0.0
        return self._stream_audio_bytes / bytes_per_second

    def _elapsed_since_request(self, timestamp: float | None) -> float:
        if timestamp is None or self._stream_request_started_at <= 0:
            return 0.0
        return max(0.0, timestamp - self._stream_request_started_at)

    def _log_stream_generation_finished(self) -> None:
        finished_at = time.perf_counter()
        elapsed = self._elapsed_since_request(finished_at)
        audio_seconds = self._stream_audio_seconds()
        generation_multiplier = audio_seconds / elapsed if elapsed > 0 else 0.0
        log_message = (
            "VoxCPM stream generation finished in %.3fs; first_byte_seconds=%.3f "
            "prebuffer_seconds=%.3f buffered_audio_seconds=%.3f generated_audio_seconds=%.3f "
            "average_generation_multiplier=%.2fx"
        )
        log_args = (
            elapsed,
            self._elapsed_since_request(self._stream_first_byte_at),
            self._elapsed_since_request(self._stream_prebuffer_reached_at),
            audio_seconds,
            audio_seconds,
            generation_multiplier,
        )
        if elapsed > 0 and generation_multiplier < 1.0:
            _LOGGER.warning(
                log_message + "; below real-time playback, consider lowering VoxCPM advanced parameters, using full WAV fallback, or increasing prebuffer.",
                *log_args,
            )
            return
        _LOGGER.info(log_message, *log_args)

    def _json_request(self, url: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        if hasattr(request, "setTransferTimeout"):
            request.setTransferTimeout(self._timeout_seconds * 1000)
        return request

    def _abort_reply(self, reply: QNetworkReply | None) -> None:
        if reply is None:
            return
        try:
            reply.abort()
        finally:
            reply.deleteLater()

    def _fail(self, message: str) -> None:
        self._stream_prebuffer_timer.stop()
        if self._stopped:
            self.finished.emit(self._request_tag)
            self.deleteLater()
            return
        self.playback_failed.emit(self._request_tag, message)
        self.finished.emit(self._request_tag)
        self.deleteLater()

    def _complete(self) -> None:
        self.finished.emit(self._request_tag)
        self.deleteLater()


class VoxCpmHttpProvider(QObject):
    playback_started = Signal(object)
    playback_failed = Signal(object, str)

    def __init__(
        self,
        *,
        endpoint: str,
        timeout_seconds: int,
        cache_dir: Path,
        audio_player: LocalWavPlayer | Any | None = None,
        stream_player: Any = None,
        stream_prebuffer_seconds: float = DEFAULT_VOXCPM_STREAM_PREBUFFER_SECONDS,
        stream_prebuffer_max_wait_seconds: float = DEFAULT_VOXCPM_STREAM_PREBUFFER_MAX_WAIT_SECONDS,
        network_manager: QNetworkAccessManager | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._cache_dir = cache_dir
        self._audio_player = audio_player or LocalWavPlayer(self)
        if stream_player is None:
            created_stream_player = StreamingPcmPlayer(prebuffer_seconds=stream_prebuffer_seconds)
            if isinstance(created_stream_player, QObject):
                created_stream_player.setParent(self)
            self._stream_player = created_stream_player
        else:
            self._stream_player = stream_player
        self._stream_prebuffer_seconds = stream_prebuffer_seconds
        self._stream_prebuffer_max_wait_seconds = stream_prebuffer_max_wait_seconds
        self._network_manager = network_manager or QNetworkAccessManager(self)
        self._last_error: str | None = None
        self._cache_counter = 0
        self._available = _is_local_http_endpoint(self._endpoint)
        self._initialization_state = (
            TtsInitializationState.READY if self._available else TtsInitializationState.UNAVAILABLE
        )
        self._current_session: VoxCpmPlaybackSession | None = None
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
        _ = accent
        return None

    def warm_up(self) -> TtsInitializationState:
        return self._initialization_state

    def speak(self, text: str, *, accent: Any | None = None, request_tag: object | None = None) -> bool:
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

        self.stop()
        session = VoxCpmPlaybackSession(
            network_manager=self._network_manager,
            endpoint=self._endpoint,
            payload=payload,
            timeout_seconds=self._timeout_seconds,
            request_tag=request_tag,
            next_audio_path=self._next_audio_path,
            audio_player=self._audio_player,
            stream_player=self._stream_player,
            stream_prebuffer_seconds=self._stream_prebuffer_seconds,
            stream_prebuffer_max_wait_seconds=self._stream_prebuffer_max_wait_seconds,
            parent=self,
        )
        session.playback_started.connect(self._on_session_started)
        session.playback_failed.connect(self._on_session_failed)
        session.finished.connect(self._on_session_finished)
        session.destroyed.connect(self._on_session_destroyed)
        self._current_session = session
        self._last_error = None
        return session.start()

    def stop(self) -> None:
        if self._current_session is not None:
            self._current_session.stop()
            self._current_session.deleteLater()
            self._current_session = None
        self._audio_player.stop()
        if self._stream_player is not None:
            self._stream_player.stop()

    def _on_session_started(self, request_tag: object | None) -> None:
        self._last_error = None
        self.playback_started.emit(request_tag)

    def _on_session_failed(self, request_tag: object | None, message: str) -> None:
        self._last_error = message
        self.playback_failed.emit(request_tag, message)

    def _on_session_finished(self, _request_tag: object | None) -> None:
        return None

    def _on_session_destroyed(self, _obj: object) -> None:
        self._current_session = None

    def _next_audio_path(self) -> Path:
        path = self._cache_dir / f"voxcpm-{self._cache_counter % 4}.wav"
        self._cache_counter += 1
        return path


class PronunciationService(QObject):
    availability_changed = Signal(bool)
    error_occurred = Signal(str)
    playback_started = Signal(object)
    playback_failed = Signal(object, str)

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
        stream_prebuffer_max_wait_seconds: float = DEFAULT_VOXCPM_STREAM_PREBUFFER_MAX_WAIT_SECONDS,
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
            stream_prebuffer_max_wait_seconds=stream_prebuffer_max_wait_seconds,
        )
        self._connect_backend_signals()

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

    def speak(self, text: str, *, accent: Any | None = None, request_tag: object | None = None) -> bool:
        if self.initialization_state is not TtsInitializationState.READY:
            return False
        result = self._backend.speak(text, accent=accent, request_tag=request_tag)
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
        stream_prebuffer_max_wait_seconds: float,
    ) -> QtTextToSpeechProvider | VoxCpmHttpProvider:
        if self._provider_name is TtsProvider.VOXCPM_LOCAL:
            return VoxCpmHttpProvider(
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
                cache_dir=cache_dir or Path.cwd() / "storage" / "tts_cache",
                stream_prebuffer_seconds=stream_prebuffer_seconds,
                stream_prebuffer_max_wait_seconds=stream_prebuffer_max_wait_seconds,
                parent=self,
            )
        return QtTextToSpeechProvider(self, accent=accent)

    def _connect_backend_signals(self) -> None:
        if not isinstance(self._backend, VoxCpmHttpProvider):
            return
        self._backend.playback_started.connect(self.playback_started.emit)
        self._backend.playback_failed.connect(self._on_backend_playback_failed)

    def _on_backend_playback_failed(self, request_tag: object | None, message: str) -> None:
        self.error_occurred.emit(message)
        self.playback_failed.emit(request_tag, message)
        self.availability_changed.emit(self.is_available)


def _is_local_http_endpoint(value: str) -> bool:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "http" and parsed.port is not None and hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _reply_header_text(reply: QNetworkReply, name: bytes, default: str) -> str:
    try:
        raw_value = reply.rawHeader(name)
    except Exception:
        return default
    if not raw_value:
        return default
    try:
        text = bytes(raw_value).decode("utf-8", errors="ignore").strip()
    except Exception:
        return default
    return text or default


def _reply_positive_int(reply: QNetworkReply, name: bytes, default: int) -> int:
    try:
        value = int(_reply_header_text(reply, name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _reply_status_code(reply: QNetworkReply) -> int | None:
    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    if status is None:
        return None
    try:
        return int(status)
    except (TypeError, ValueError):
        return None
