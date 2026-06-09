from __future__ import annotations

from collections.abc import Iterable
from random import randint
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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


def _enum_name(value: Any) -> str:
    if value is None:
        return "bottom_right"
    if isinstance(value, str):
        return value.strip().lower()

    for attr in ("value", "name"):
        enum_value = getattr(value, attr, None)
        if isinstance(enum_value, str):
            return enum_value.strip().lower()

    return str(value).strip().lower()


def _normalize_position(value: Any) -> str:
    raw = _enum_name(value)
    return _POSITION_ALIASES.get(raw, "bottom_right")


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


def _coerce_text_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("|", ";").split(";")]
        return [part for part in parts if part]
    if isinstance(value, Iterable):
        lines: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                lines.append(item.strip())
        return lines
    return []


def _format_summary(entry: Any) -> str:
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
        lines = _coerce_text_lines(getattr(entry, name, None))
        if lines:
            return " / ".join(lines[:3])
    return "暂无释义。"


def _format_details(entry: Any) -> str:
    detail_lines: list[str] = []

    definitions = _coerce_text_lines(getattr(entry, "chinese_definitions", None))
    if not definitions:
        definitions = _coerce_text_lines(getattr(entry, "definitions", None))
    if not definitions:
        summary = _format_summary(entry)
        definitions = [summary] if summary else []

    if definitions:
        detail_lines.append("释义")
        detail_lines.extend(f"- {line}" for line in definitions)

    for label, attr in (("例句", "examples"), ("短语", "phrases"), ("备注", "notes")):
        lines = _coerce_text_lines(getattr(entry, attr, None))
        if lines:
            detail_lines.append("")
            detail_lines.append(label)
            detail_lines.extend(f"- {line}" for line in lines)

    return "\n".join(detail_lines).strip() or "暂无更多详情。"


def _screen_rect(anchor: QPoint | None = None) -> QRect:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return QRect(0, 0, 1280, 720)

    screen = app.screenAt(anchor or QCursor.pos()) or app.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1280, 720)
    return screen.availableGeometry()


def compute_popup_rect(size: QSize, position: Any, anchor: QPoint | None = None, margin: int = 24) -> QRect:
    position_name = _normalize_position(position)
    screen = _screen_rect(anchor)
    width = min(size.width(), screen.width())
    height = min(size.height(), screen.height())

    if position_name == "near_mouse":
        mouse = anchor or QCursor.pos()
        x = mouse.x() + 18
        y = mouse.y() + 18
        if x + width > screen.right() - margin:
            x = mouse.x() - width - 18
        if y + height > screen.bottom() - margin:
            y = mouse.y() - height - 18
    elif position_name == "top_center":
        x = screen.x() + (screen.width() - width) // 2
        y = screen.y() + margin
    elif position_name == "center":
        x = screen.x() + (screen.width() - width) // 2
        y = screen.y() + (screen.height() - height) // 2
    elif position_name == "random":
        min_x = screen.x() + margin
        max_x = max(min_x, screen.right() - width - margin)
        min_y = screen.y() + margin
        max_y = max(min_y, screen.bottom() - height - margin)
        x = randint(min_x, max_x)
        y = randint(min_y, max_y)
    else:
        x = screen.right() - width - margin
        y = screen.bottom() - height - margin

    x = max(screen.x() + margin, min(x, screen.right() - width - margin))
    y = max(screen.y() + margin, min(y, screen.bottom() - height - margin))
    return QRect(x, y, width, height)


class CardPopup(QFrame):
    pronounce = Signal(str)
    toggle_details = Signal(bool)
    mark_mastered = Signal(str)
    reviewed = Signal(str, bool)
    snoozed = Signal(str)
    dismissed = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry: Any | None = None
        self._position_mode: str = "bottom_right"
        self._details_expanded = False
        self._auto_hide_enabled = True
        self._hovered = False
        self._pending_hide_ms = 0
        self._drag_offset: QPoint | None = None
        self._manual_positioned = False

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._hide_if_allowed)

        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setObjectName("cardPopup")
        self.setMouseTracking(True)

        self._build_ui()
        self.setFixedWidth(420)
        self._sync_details_visibility()

    @property
    def current_entry(self) -> Any | None:
        return self._entry

    def set_entry(self, entry: Any) -> None:
        self._entry = entry
        term = _first_text(entry, "term", "word", "text") or "单词"
        ipa = _first_text(entry, "ipa", "pronunciation", "phonetic")
        summary = _format_summary(entry)
        details = _format_details(entry)

        self.word_label.setText(term)
        self.ipa_label.setText(ipa or "/.../")
        self.summary_label.setText(summary)
        self.details_label.setText(details)

        self.details_button.setEnabled(bool(details.strip()))
        self.mastered_button.setEnabled(bool(term))
        self.pronounce_button.setEnabled(bool(term))
        self.snooze_button.setEnabled(bool(term))

        self._refresh_layout_size()

    def set_position_mode(self, position: Any) -> None:
        self._position_mode = _normalize_position(position)

    def reposition(self, position: Any | None = None, anchor: QPoint | None = None) -> None:
        if position is not None:
            self.set_position_mode(position)
        self._refresh_layout_size()
        rect = compute_popup_rect(self.sizeHint(), self._position_mode, anchor=anchor)
        self.setGeometry(rect)

    def show_popup(
        self,
        entry: Any,
        position: Any | None = None,
        *,
        anchor: QPoint | None = None,
        auto_hide_ms: int | None = None,
    ) -> None:
        self._manual_positioned = False
        self.set_entry(entry)
        self.reposition(position=position, anchor=anchor)
        self.show()
        self.raise_()
        if auto_hide_ms:
            self.start_auto_hide(auto_hide_ms)

    def start_auto_hide(self, delay_ms: int) -> None:
        self._pending_hide_ms = max(0, delay_ms)
        if self._auto_hide_enabled and not self._hovered and self._pending_hide_ms > 0:
            self._auto_hide_timer.start(self._pending_hide_ms)

    def stop_auto_hide(self) -> None:
        self._auto_hide_timer.stop()

    def set_hover_aware_auto_hide(self, enabled: bool) -> None:
        self._auto_hide_enabled = enabled
        if not enabled:
            self.stop_auto_hide()

    def is_details_expanded(self) -> bool:
        return self._details_expanded

    def set_details_expanded(self, expanded: bool) -> None:
        if self._details_expanded == expanded:
            return
        self._details_expanded = expanded
        self._sync_details_visibility()
        self.toggle_details.emit(expanded)
        self._refresh_layout_size()
        if self.isVisible() and not self._manual_positioned:
            self.reposition()

    def closeEvent(self, event: Any) -> None:
        self.stop_auto_hide()
        self.closed.emit()
        super().closeEvent(event)

    def enterEvent(self, event: Any) -> None:
        self._hovered = True
        self.stop_auto_hide()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self._hovered = False
        if self._auto_hide_enabled and self._pending_hide_ms > 0 and self.isVisible():
            self._auto_hide_timer.start(self._pending_hide_ms)
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
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame(self)
        card.setObjectName("cardSurface")
        outer_layout.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QGridLayout()
        header.setHorizontalSpacing(10)
        header.setVerticalSpacing(4)
        layout.addLayout(header)

        self.word_label = QLabel("单词", card)
        self.word_label.setObjectName("wordLabel")
        self.word_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header.addWidget(self.word_label, 0, 0)

        self.close_button = QPushButton("×", card)
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(28, 28)
        self.close_button.clicked.connect(self._request_dismiss)
        header.addWidget(self.close_button, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.ipa_label = QLabel("/.../", card)
        self.ipa_label.setObjectName("ipaLabel")
        header.addWidget(self.ipa_label, 1, 0)

        self.summary_label = QLabel("暂无释义。", card)
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        layout.addLayout(actions)

        self.pronounce_button = QPushButton("朗读", card)
        self.pronounce_button.clicked.connect(self._emit_pronounce)
        actions.addWidget(self.pronounce_button)

        self.details_button = QPushButton("展开详情", card)
        self.details_button.clicked.connect(self._toggle_details)
        actions.addWidget(self.details_button)

        self.known_button = QPushButton("认识", card)
        self.known_button.clicked.connect(lambda: self._emit_reviewed(True))
        actions.addWidget(self.known_button)

        self.unknown_button = QPushButton("不认识", card)
        self.unknown_button.clicked.connect(lambda: self._emit_reviewed(False))
        actions.addWidget(self.unknown_button)

        self.snooze_button = QPushButton("稍后", card)
        self.snooze_button.clicked.connect(self._emit_snoozed)
        actions.addWidget(self.snooze_button)

        self.mastered_button = QPushButton("已掌握", card)
        self.mastered_button.clicked.connect(self._emit_mastered)
        actions.addWidget(self.mastered_button)

        actions.addStretch(1)

        self.details_container = QFrame(card)
        self.details_container.setObjectName("detailsContainer")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 8, 0, 0)
        details_layout.setSpacing(0)

        self.details_label = QLabel("暂无更多详情。", self.details_container)
        self.details_label.setObjectName("detailsLabel")
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self.details_label)
        layout.addWidget(self.details_container)

        self.setStyleSheet(
            """
            QFrame#cardSurface {
                background: #f7f4ec;
                border: 1px solid #d8cdb8;
                border-radius: 16px;
            }
            QLabel#wordLabel {
                color: #2b2318;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#ipaLabel {
                color: #7a6543;
                font-size: 13px;
            }
            QLabel#summaryLabel {
                color: #3b3021;
                font-size: 15px;
            }
            QLabel#detailsLabel {
                color: #584732;
                font-size: 13px;
            }
            QFrame#detailsContainer {
                border-top: 1px solid #e2d7c4;
            }
            QPushButton {
                background: #efe3cc;
                border: 1px solid #d0b98f;
                border-radius: 10px;
                color: #322819;
                font-size: 12px;
                font-weight: 600;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background: #f6ead4;
            }
            QPushButton#closeButton {
                background: transparent;
                border: none;
                color: #7a6543;
                font-size: 16px;
                padding: 0;
            }
            QPushButton#closeButton:hover {
                color: #2b2318;
            }
            """
        )
        for draggable in (
            card,
            self.word_label,
            self.ipa_label,
            self.summary_label,
            self.details_container,
        ):
            draggable.installEventFilter(self)
            draggable.setMouseTracking(True)

    def _refresh_layout_size(self) -> None:
        self.adjustSize()
        hint = self.sizeHint()
        self.resize(max(420, hint.width()), hint.height())

    def _sync_details_visibility(self) -> None:
        self.details_container.setVisible(self._details_expanded)
        self.details_button.setText("收起详情" if self._details_expanded else "展开详情")

    def _toggle_details(self) -> None:
        self.set_details_expanded(not self._details_expanded)

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

    def _begin_drag(self, event: Any) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self.stop_auto_hide()
        self._drag_offset = _event_global_pos(event) - self.frameGeometry().topLeft()
        self._manual_positioned = True
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
        if self._auto_hide_enabled and not self._hovered and self._pending_hide_ms > 0 and self.isVisible():
            self._auto_hide_timer.start(self._pending_hide_ms)
        event.accept()
        return True

    def _hide_if_allowed(self) -> None:
        if not self._hovered:
            self.close()
