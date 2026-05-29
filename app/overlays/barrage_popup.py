from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from app.models import WordEntry


_POSITION_ALIASES = {
    "near_mouse": "near_mouse",
    "bottom_right": "bottom_right",
    "top_center": "top_center",
    "center": "center",
}


def _enum_name(value: Any) -> str:
    if value is None:
        return "top_center"
    if isinstance(value, str):
        return value.strip().lower()

    for attr in ("value", "name"):
        enum_value = getattr(value, attr, None)
        if isinstance(enum_value, str):
            return enum_value.strip().lower()

    return str(value).strip().lower()


def _normalize_position(value: Any) -> str:
    raw = _enum_name(value)
    return _POSITION_ALIASES.get(raw, "top_center")


def _first_text(source: Any, *names: str) -> str:
    for name in names:
        value = getattr(source, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _coerce_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("|", ";").split(";")]
        return [part for part in parts if part]
    if isinstance(value, Iterable):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _summary_text(entry: Any) -> str:
    direct = _first_text(
        entry,
        "chinese_summary",
        "summary",
        "definition",
        "translation",
        "meaning",
    )
    if direct:
        return direct

    for name in ("chinese_definitions", "definitions", "meanings", "translations"):
        lines = _coerce_lines(getattr(entry, name, None))
        if lines:
            return " / ".join(lines[:2])
    return "No definition available."


def _screen_rect(anchor: QPoint | None = None) -> QRect:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return QRect(0, 0, 1280, 720)

    screen = app.screenAt(anchor or QCursor.pos()) or app.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1280, 720)
    return screen.availableGeometry()


def compute_barrage_rect(size: QSize, position: Any, anchor: QPoint | None = None, margin: int = 20) -> QRect:
    position_name = _normalize_position(position)
    screen = _screen_rect(anchor)
    width = min(size.width(), screen.width())
    height = min(size.height(), screen.height())

    if position_name == "near_mouse":
        mouse = anchor or QCursor.pos()
        y = mouse.y() - height - 16
        if y < screen.y() + margin:
            y = mouse.y() + 16
    elif position_name == "bottom_right":
        y = screen.bottom() - height - margin
    elif position_name == "center":
        y = screen.y() + (screen.height() - height) // 2
    else:
        y = screen.y() + margin

    y = max(screen.y() + margin, min(y, screen.bottom() - height - margin))
    return QRect(screen.right() - width - margin, y, width, height)


class BarragePopup(QFrame):
    pronounce = Signal(str)
    mark_mastered = Signal(str)
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry: Any | None = None
        self._position_mode: str = "top_center"
        self._animation = QPropertyAnimation(self, b"pos", self)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.finished.connect(self._handle_animation_finished)

        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setObjectName("barragePopup")

        self._build_ui()
        self.setFixedWidth(520)

    @property
    def current_entry(self) -> Any | None:
        return self._entry

    def set_entry(self, entry: Any) -> None:
        self._entry = entry
        term = _first_text(entry, "term", "word", "text") or "Word"
        ipa = _first_text(entry, "ipa", "pronunciation", "phonetic")
        summary = _summary_text(entry)

        self.word_label.setText(term)
        self.ipa_label.setText(ipa or "/.../")
        self.summary_label.setText(summary)

        self.pronounce_button.setEnabled(bool(term))
        self.mastered_button.setEnabled(bool(term))

        self._refresh_size()

    def set_position_mode(self, position: Any) -> None:
        self._position_mode = _normalize_position(position)

    def reposition(self, position: Any | None = None, *, anchor: QPoint | None = None) -> None:
        if position is not None:
            self.set_position_mode(position)
        self._refresh_size()
        self.setGeometry(compute_barrage_rect(self.sizeHint(), self._position_mode, anchor=anchor))

    def show_popup(
        self,
        entry: Any,
        position: Any | None = None,
        *,
        anchor: QPoint | None = None,
        duration_ms: int = 9000,
    ) -> None:
        self.set_entry(entry)
        self.reposition(position=position, anchor=anchor)
        self.show()
        self.raise_()
        self.start_animation(duration_ms=duration_ms, anchor=anchor)

    def start_animation(self, duration_ms: int = 9000, anchor: QPoint | None = None) -> None:
        self._refresh_size()
        rect = compute_barrage_rect(self.sizeHint(), self._position_mode, anchor=anchor)
        screen = _screen_rect(anchor)
        start = QPoint(screen.right() + 12, rect.y())
        end = QPoint(screen.x() - rect.width() - 12, rect.y())

        self._animation.stop()
        self.move(start)
        self._animation.setDuration(max(1000, duration_ms))
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()

    def stop_animation(self) -> None:
        self._animation.stop()

    def closeEvent(self, event: Any) -> None:
        self.stop_animation()
        self.closed.emit()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)

        surface = QFrame(self)
        surface.setObjectName("surface")
        outer.addWidget(surface)

        row = QHBoxLayout(surface)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(10)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        row.addLayout(text_column, stretch=1)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        text_column.addLayout(top_row)

        self.word_label = QLabel("Word", surface)
        self.word_label.setObjectName("wordLabel")
        top_row.addWidget(self.word_label)

        self.ipa_label = QLabel("/.../", surface)
        self.ipa_label.setObjectName("ipaLabel")
        top_row.addWidget(self.ipa_label)
        top_row.addStretch(1)

        self.summary_label = QLabel("No definition available.", surface)
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setWordWrap(True)
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_column.addWidget(self.summary_label)

        self.pronounce_button = QPushButton("Speak", surface)
        self.pronounce_button.setObjectName("miniButton")
        self.pronounce_button.clicked.connect(self._emit_pronounce)
        row.addWidget(self.pronounce_button)

        self.mastered_button = QPushButton("Mastered", surface)
        self.mastered_button.setObjectName("miniButton")
        self.mastered_button.clicked.connect(self._emit_mastered)
        row.addWidget(self.mastered_button)

        self.close_button = QPushButton("x", surface)
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.close)
        row.addWidget(self.close_button)

        self.setStyleSheet(
            """
            QFrame#surface {
                background: rgba(31, 37, 45, 232);
                border: 1px solid rgba(255, 255, 255, 38);
                border-radius: 16px;
            }
            QLabel#wordLabel {
                color: #f8f5ee;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#ipaLabel {
                color: #d6c9b0;
                font-size: 12px;
            }
            QLabel#summaryLabel {
                color: #edf0f4;
                font-size: 13px;
            }
            QPushButton#miniButton {
                background: rgba(255, 255, 255, 28);
                border: 1px solid rgba(255, 255, 255, 46);
                border-radius: 9px;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 10px;
            }
            QPushButton#miniButton:hover {
                background: rgba(255, 255, 255, 44);
            }
            QPushButton#closeButton {
                background: transparent;
                border: none;
                color: #f8f5ee;
                font-size: 16px;
                padding: 0;
            }
            QPushButton#closeButton:hover {
                color: #ffffff;
            }
            """
        )

    def _refresh_size(self) -> None:
        self.adjustSize()
        hint = self.sizeHint()
        self.resize(max(460, hint.width()), hint.height())

    def _entry_term(self) -> str:
        if self._entry is None:
            return ""
        return _first_text(self._entry, "term", "word", "text")

    def _emit_pronounce(self) -> None:
        term = self._entry_term()
        if term:
            self.pronounce.emit(term)

    def _emit_mastered(self) -> None:
        term = self._entry_term()
        if term:
            self.mark_mastered.emit(term)

    def _handle_animation_finished(self) -> None:
        if self.isVisible():
            self.close()
