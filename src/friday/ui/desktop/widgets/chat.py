"""Fil de discussion : bulles de l'utilisateur à droite, de Friday à gauche."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from friday.ui.desktop.widgets.confirm_card import ConfirmCard

BUBBLE_RATIO = 0.8  # largeur max d'une bulle, en part de la largeur du chat
H_MARGIN = 14


class Bubble(QFrame):
    def __init__(self, author: str, text: str, from_user: bool) -> None:
        super().__init__()
        self.setObjectName("BubbleUser" if from_user else "BubbleFriday")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(H_MARGIN, 8, H_MARGIN, 10)
        layout.setSpacing(2)

        header = QLabel(author, objectName="BubbleAuthor")
        header.setAlignment(Qt.AlignRight if from_user else Qt.AlignLeft)
        self.label = QLabel(text, objectName="BubbleText")
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(header)
        layout.addWidget(self.label)
        self._max_width = 400

    def append(self, text: str) -> None:
        self.label.setText(self.label.text() + text)
        self._fit_text()

    def fit(self, max_width: int) -> None:
        self._max_width = max_width
        self.setMaximumWidth(max_width)
        self._fit_text()

    def _fit_text(self) -> None:
        # Un QLabel avec retour à la ligne se fait le plus étroit possible : on lui donne
        # la largeur de son texte (sur une ligne), dans la limite de la bulle.
        self.label.ensurePolished()  # applique la police du thème avant de mesurer
        text_width = max(
            self.label.fontMetrics().horizontalAdvance(line)
            for line in self.label.text().splitlines() or [""]
        )
        self.label.setMinimumWidth(min(text_width + 2, self._max_width - 2 * H_MARGIN))


class ChatView(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self._layout.setSpacing(10)
        self._layout.addStretch()
        self.setWidget(container)
        self._bubbles: list[Bubble] = []
        self._cards: list[ConfirmCard] = []
        self._current: Bubble | None = None
        # Reste collé en bas quand le contenu grandit
        self.verticalScrollBar().rangeChanged.connect(
            lambda _min, maximum: self.verticalScrollBar().setValue(maximum)
        )

    def add_user(self, text: str, by_voice: bool) -> None:
        self._add_bubble(Bubble("VOUS 🎙" if by_voice else "VOUS", text, from_user=True), True)

    def start_reply(self) -> None:
        self._current = None  # la bulle naît avec le premier mot

    def append_reply(self, text: str) -> None:
        if self._current is None:
            self._current = Bubble("FRIDAY", "", from_user=False)
            self._add_bubble(self._current, False)
        self._current.append(text)

    def end_reply(self, interrupted: bool) -> None:
        if self._current and interrupted:
            self._current.append(" […]")
        self._current = None
        for card in self._cards:  # réponse finie : les questions en suspens sont closes
            card.close_card()
        self._cards.clear()

    def add_confirmation(self, question: str) -> ConfirmCard:
        card = ConfirmCard(question)
        self._layout.addWidget(card)
        self._cards.append(card)
        self._current = None  # la suite de la réponse s'affiche sous la carte
        return card

    def add_tool(self, label: str) -> None:
        self.add_notice(label, "ToolNotice")
        self._current = None  # la suite de la réponse s'affiche sous l'outil

    def add_notice(self, text: str, kind: str = "Notice") -> None:
        label = QLabel(text, objectName=kind)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        self._layout.addWidget(label)

    def clear(self) -> None:
        while self._layout.count() > 1:  # on garde l'espace extensible du haut
            _delete_item(self._layout.takeAt(1))
        self._bubbles.clear()
        self._current = None

    def _add_bubble(self, bubble: Bubble, from_user: bool) -> None:
        row = QHBoxLayout()
        if from_user:
            row.addStretch()
        row.addWidget(bubble)
        if not from_user:
            row.addStretch()
        self._layout.addLayout(row)
        self._bubbles.append(bubble)
        self._fit(bubble)

    def _fit(self, bubble: Bubble) -> None:
        bubble.fit(int(self.viewport().width() * BUBBLE_RATIO))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        for bubble in self._bubbles:
            self._fit(bubble)


def _delete_item(item) -> None:
    if item.widget():
        item.widget().deleteLater()
    elif item.layout():
        layout = item.layout()
        while layout.count():
            _delete_item(layout.takeAt(0))
        layout.deleteLater()
