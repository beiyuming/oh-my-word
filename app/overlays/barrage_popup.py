from __future__ import annotations

from collections.abc import Iterable
from random import randint
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QAbstractAnimation, QEvent, QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt, Signal
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
    "random": "random",
}
_DRIFT_PIXELS_PER_SECOND = 140


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


def _event_global_pos(event: Any) -> QPoint:
    global_position = getattr(event, "globalPosition", lambda: None)()
    if global_position is not None and hasattr(global_position, "toPoint"):
        return global_position.toPoint()
    global_pos = getattr(event, "globalPos", lambda: QPoint())()
    return global_pos if isinstance(global_pos, QPoint) else QPoint()


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
    return "暂无释义。"


def _details_text(entry: Any) -> str:
    detail_lines: list[str] = []

    definitions = _coerce_lines(getattr(entry, "chinese_definitions", None))
    if not definitions:
        definitions = _coerce_lines(getattr(entry, "definitions", None))
    if not definitions:
        summary = _summary_text(entry)
        definitions = [summary] if summary else []

    if definitions:
        detail_lines.append("释义")
        detail_lines.extend(f"- {line}" for line in definitions)

    example_lines = _example_lines(entry)
    if example_lines:
        detail_lines.append("")
        detail_lines.append("例句")
        detail_lines.extend(f"- {line}" for line in example_lines)

    for label, attr in (("短语", "phrases"), ("备注", "notes")):
        lines = _coerce_lines(getattr(entry, attr, None))
        if lines:
            detail_lines.append("")
            detail_lines.append(label)
            detail_lines.extend(f"- {line}" for line in lines)

    return "\n".join(detail_lines).strip() or "暂无更多详情。"


def _example_lines(entry: Any) -> list[str]:
    lines: list[str] = []
    for line in (
        _first_text(entry, "example_sentence", "sentence", "example"),
        _first_text(entry, "example_translation", "example_cn", "translation_example"),
    ):
        if line and line not in lines:
            lines.append(line)

    for line in _coerce_lines(getattr(entry, "examples", None)):
        if line not in lines:
            lines.append(line)
    return lines


def _pronunciation_text(entry: Any) -> str:
    term = _first_text(entry, "term", "word", "text")
    example_sentence = _first_text(entry, "example_sentence", "sentence", "example")
    if term and example_sentence and example_sentence.casefold() != term.casefold():
        return f"{term}. {example_sentence}"
    return term or example_sentence


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
    x = screen.x() + (screen.width() - width) // 2

    if position_name == "near_mouse":
        mouse = anchor or QCursor.pos()
        x = mouse.x() + 16
        y = mouse.y() - height - 16
        if x + width > screen.right() - margin:
            x = mouse.x() - width - 16
        if y < screen.y() + margin:
            y = mouse.y() + 16
    elif position_name == "bottom_right":
        x = screen.right() - width - margin
        y = screen.bottom() - height - margin
    elif position_name == "center":
        y = screen.y() + (screen.height() - height) // 2
    elif position_name == "random":
        min_y = screen.y() + margin
        max_y = max(min_y, screen.bottom() - height - margin)
        y = randint(min_y, max_y)
    else:
        y = screen.y() + margin

    x = max(screen.x() + margin, min(x, screen.right() - width - margin))
    y = max(screen.y() + margin, min(y, screen.bottom() - height - margin))
    return QRect(x, y, width, height)


class BarragePopup(QFrame):
    pronounce = Signal(str)
    mark_mastered = Signal(str)
    reviewed = Signal(str, bool)
    snoozed = Signal(str)
    dismissed = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry: Any | None = None
        self._position_mode: str = "top_center"
        self._animation_phase = "idle"
        self._details_expanded = False
        self._paused_by_hover = False
        self._drag_offset: QPoint | None = None
        self._exit_target = QPoint()
        self._animation = QPropertyAnimation(self, b"pos", self)
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
        self.setMinimumWidth(520)

    @property
    def current_entry(self) -> Any | None:
        return self._entry

    def set_entry(self, entry: Any) -> None:
        self._entry = entry
        term = _first_text(entry, "term", "word", "text") or "单词"
        ipa = _first_text(entry, "ipa", "pronunciation", "phonetic")
        summary = _summary_text(entry)
        details = _details_text(entry)

        self.word_label.setText(term)
        self.ipa_label.setText(ipa or "/.../")
        self.summary_label.setText(summary)
        self.details_label.setText(details)

        self.pronounce_button.setEnabled(bool(term))
        self.mastered_button.setEnabled(bool(term))
        self.snooze_button.setEnabled(bool(term))
        self.details_button.setEnabled(bool(details.strip()))
        self.set_details_expanded(False, pause=False)

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
    ) -> None:
        self.set_entry(entry)
        self.reposition(position=position, anchor=anchor)
        self.show()
        self.raise_()
        self.start_animation(anchor=anchor)

    def start_animation(self, anchor: QPoint | None = None) -> None:
        self._refresh_size()
        rect = compute_barrage_rect(self.sizeHint(), self._position_mode, anchor=anchor)
        screen = _screen_rect(anchor)
        start = QPoint(screen.right() + 12, rect.y())
        end = QPoint(screen.x() - self.width() - 12, rect.y())
        self._start_drift(start, end)

    def _start_drift(self, start: QPoint, end: QPoint) -> None:
        distance = max(1, start.x() - end.x())
        drift_ms = max(7000, int(distance / _DRIFT_PIXELS_PER_SECOND * 1000))
        self._animation.stop()
        self._animation_phase = "drift"
        self._paused_by_hover = False
        self.move(start)
        self._animation.setDuration(drift_ms)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()

    def stop_animation(self) -> None:
        self._animation.stop()
        self._animation_phase = "idle"
        self._paused_by_hover = False
        self._drag_offset = None

    def is_details_expanded(self) -> bool:
        return self._details_expanded

    def set_details_expanded(self, expanded: bool, *, pause: bool = True) -> None:
        self._details_expanded = expanded
        self._sync_details_visibility()
        if expanded and pause:
            self.stop_animation()
        self._refresh_size()

    def closeEvent(self, event: Any) -> None:
        self.stop_animation()
        self.closed.emit()
        super().closeEvent(event)

    def enterEvent(self, event: Any) -> None:
        if not self._details_expanded:
            self._pause_for_reading()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        if self._paused_by_hover and not self._details_expanded and self.isVisible():
            self._paused_by_hover = False
            if self._animation_phase == "drift" and self._animation.state() == QAbstractAnimation.State.Paused:
                self._animation.resume()
        super().leaveEvent(event)

    def eventFilter(self, watched: Any, event: Any) -> bool:
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress:
            return self._begin_drag(event)
        if event_type == QEvent.Type.MouseMove:
            return self._drag_to(event)
        if event_type == QEvent.Type.MouseButtonRelease:
            return self._finish_drag(event)
        return super().eventFilter(watched, event)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)

        surface = QFrame(self)
        surface.setObjectName("surface")
        outer.addWidget(surface)

        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(16, 12, 16, 12)
        surface_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        surface_layout.addLayout(header_row)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        header_row.addLayout(text_column, stretch=1)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        text_column.addLayout(top_row)

        self.word_label = QLabel("单词", surface)
        self.word_label.setObjectName("wordLabel")
        self.word_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        top_row.addWidget(self.word_label)

        self.ipa_label = QLabel("/.../", surface)
        self.ipa_label.setObjectName("ipaLabel")
        self.ipa_label.setMinimumWidth(96)
        self.ipa_label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        top_row.addWidget(self.ipa_label)
        top_row.addStretch(1)

        self.summary_label = QLabel("暂无释义。", surface)
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setWordWrap(True)
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_column.addWidget(self.summary_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.setContentsMargins(0, 0, 0, 0)
        header_row.addLayout(action_row)

        self.pronounce_button = QPushButton("朗读", surface)
        self.pronounce_button.setObjectName("miniButton")
        self.pronounce_button.clicked.connect(self._emit_pronounce)
        action_row.addWidget(self.pronounce_button)

        self.details_button = QPushButton("详情", surface)
        self.details_button.setObjectName("miniButton")
        self.details_button.clicked.connect(self._toggle_details)
        action_row.addWidget(self.details_button)

        self.known_button = QPushButton("认识", surface)
        self.known_button.setObjectName("miniButton")
        self.known_button.clicked.connect(lambda: self._emit_reviewed(True))
        action_row.addWidget(self.known_button)

        self.unknown_button = QPushButton("不认识", surface)
        self.unknown_button.setObjectName("miniButton")
        self.unknown_button.clicked.connect(lambda: self._emit_reviewed(False))
        action_row.addWidget(self.unknown_button)

        self.snooze_button = QPushButton("稍后", surface)
        self.snooze_button.setObjectName("miniButton")
        self.snooze_button.clicked.connect(self._emit_snoozed)
        action_row.addWidget(self.snooze_button)

        self.mastered_button = QPushButton("已掌握", surface)
        self.mastered_button.setObjectName("miniButton")
        self.mastered_button.clicked.connect(self._emit_mastered)
        action_row.addWidget(self.mastered_button)

        self.close_button = QPushButton("×", surface)
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self._request_dismiss)
        action_row.addWidget(self.close_button)

        self.details_container = QFrame(surface)
        self.details_container.setObjectName("detailsContainer")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 8, 0, 0)
        details_layout.setSpacing(0)

        self.details_label = QLabel("暂无更多详情。", self.details_container)
        self.details_label.setObjectName("detailsLabel")
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self.details_label)
        surface_layout.addWidget(self.details_container)

        self.setStyleSheet(
            """
            QFrame#surface {
                background: rgba(255, 255, 255, 218);
                border: 1px solid rgba(0, 0, 0, 85);
                border-radius: 16px;
            }
            QLabel#wordLabel {
                color: #111111;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#ipaLabel {
                color: #333333;
                font-size: 12px;
            }
            QLabel#summaryLabel {
                color: #111111;
                font-size: 13px;
            }
            QLabel#detailsLabel {
                color: #111111;
                font-size: 13px;
            }
            QFrame#detailsContainer {
                border-top: 1px solid rgba(0, 0, 0, 55);
            }
            QPushButton#miniButton {
                background: rgba(255, 255, 255, 120);
                border: 1px solid rgba(0, 0, 0, 65);
                border-radius: 9px;
                color: #111111;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 10px;
            }
            QPushButton#miniButton:hover {
                background: rgba(255, 255, 255, 180);
            }
            QPushButton#closeButton {
                background: transparent;
                border: none;
                color: #111111;
                font-size: 16px;
                padding: 0;
            }
            QPushButton#closeButton:hover {
                color: #000000;
            }
            """
        )
        self._sync_details_visibility()
        for draggable in (
            surface,
            self.word_label,
            self.ipa_label,
            self.summary_label,
            self.details_container,
        ):
            draggable.installEventFilter(self)
            draggable.setMouseTracking(True)

    def _refresh_size(self) -> None:
        self.adjustSize()
        hint = self.sizeHint()
        self.resize(max(460, hint.width()), hint.height())

    def _entry_term(self) -> str:
        if self._entry is None:
            return ""
        return _first_text(self._entry, "term", "word", "text")

    def _emit_pronounce(self) -> None:
        if self._entry is None:
            return
        text = _pronunciation_text(self._entry)
        if text:
            self.pronounce.emit(text)

    def _emit_mastered(self) -> None:
        term = self._entry_term()
        if term:
            self.mark_mastered.emit(term)

    def _emit_reviewed(self, known: bool) -> None:
        term = self._entry_term()
        if term:
            self.reviewed.emit(term, known)

    def _emit_snoozed(self) -> None:
        term = self._entry_term()
        if term:
            self.snoozed.emit(term)

    def _request_dismiss(self) -> None:
        self.dismissed.emit()
        self.close()

    def _toggle_details(self) -> None:
        self.set_details_expanded(not self._details_expanded)

    def _sync_details_visibility(self) -> None:
        self.details_container.setVisible(self._details_expanded)
        self.details_button.setText("收起" if self._details_expanded else "详情")

    def _pause_for_reading(self) -> None:
        if not self.isVisible():
            return
        if self._animation_phase == "drift" and self._animation.state() == QAbstractAnimation.State.Running:
            self._animation.pause()
            self._paused_by_hover = True

    def _begin_drag(self, event: Any) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self._animation.stop()
        self._drag_offset = _event_global_pos(event) - self.frameGeometry().topLeft()
        self._paused_by_hover = False
        event.accept()
        return True

    def _drag_to(self, event: Any) -> bool:
        if self._drag_offset is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return False
        self.move(_event_global_pos(event) - self._drag_offset)
        event.accept()
        return True

    def _finish_drag(self, event: Any) -> bool:
        if self._drag_offset is None:
            return False
        self._drag_offset = None
        if not self._details_expanded and self.isVisible():
            screen = _screen_rect(self.geometry().center())
            start = self.pos()
            end = QPoint(screen.x() - self.width() - 12, start.y())
            if start.x() <= end.x():
                self.close()
            else:
                self._start_drift(start, end)
        event.accept()
        return True

    def _handle_animation_finished(self) -> None:
        if self._animation_phase == "drift" and self.isVisible():
            self._animation_phase = "idle"
            self.close()
