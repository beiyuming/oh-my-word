from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QLocale, Signal

try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except ImportError:  # pragma: no cover - depends on optional Qt module
    QTextToSpeech = None  # type: ignore[assignment]


class PronunciationService(QObject):
    """Best-effort offline TTS wrapper with English voice preference selection."""

    availability_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        accent: Any | None = None,
        on_error: Callable[[str], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._configured_accent = accent
        self._backend: QTextToSpeech | None = None
        self._available = False
        self._last_error: str | None = None

        if on_error is not None:
            self.error_occurred.connect(on_error)

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
            self._configured_accent = accent
            self._apply_voice_preference()
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
            self.availability_changed.emit(False)
            return

        try:
            self._backend = QTextToSpeech(self)
        except Exception as exc:  # pragma: no cover - backend-specific failure
            self._report_error(f"Qt text-to-speech backend failed to initialize: {exc}")
            self.availability_changed.emit(False)
            return

        self._apply_voice_preference()
        self.availability_changed.emit(self._available)

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
            self._available = False
            self.availability_changed.emit(False)
            return

        preferred_voice = self._select_voice(voices, self._configured_accent)
        if preferred_voice is not None:
            try:
                self._backend.setVoice(preferred_voice)
            except Exception as exc:  # pragma: no cover - backend-specific failure
                self._report_error(f"Could not select text-to-speech voice: {exc}")
                self.availability_changed.emit(False)
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
        self.error_occurred.emit(message)
