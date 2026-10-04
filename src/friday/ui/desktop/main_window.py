"""Fenêtre principale, sans bordure et arrondie : barre de titre, noyau holographique,
fil de discussion, barre de saisie. Toute l'interface suit la couleur choisie."""

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from friday.app.assistant import Assistant
from friday.app.events import AssistantState
from friday.core.config import Settings
from friday.ui.desktop import preferences, theme
from friday.ui.desktop.bridge import QtBridge
from friday.ui.desktop.popups.manager import PopupManager
from friday.ui.desktop.widgets.chat import ChatView
from friday.ui.desktop.widgets.frame import ResizableFrame
from friday.ui.desktop.widgets.holo import HoloOrb
from friday.ui.desktop.widgets.input_bar import InputBar
from friday.ui.desktop.widgets.title_bar import TitleBar

MAX_CONTENT_WIDTH = 820


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, assistant: Assistant | None = None,
                 preferences_path: Path = preferences.PATH) -> None:  # fmt: skip
        super().__init__()
        self.setWindowTitle("F.R.I.D.A.Y.")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)  # coins arrondis
        self.resize(540, 860)
        self.setMinimumSize(420, 620)
        self._preferences_path = preferences_path
        saved = preferences.load(preferences_path).get("color")
        self.base = theme.parse_color(saved or settings.interface_color)

        self.bridge = QtBridge()
        self.assistant = assistant or Assistant(settings, self.bridge)
        self.state = AssistantState.LOADING

        self.title_bar = TitleBar(self, self.base)
        self.orb = HoloOrb()
        self.orb.setFixedHeight(270)
        self.status = QLabel(objectName="Status", alignment=Qt.AlignCenter)
        self.info = QLabel(objectName="Info", alignment=Qt.AlignCenter, wordWrap=True)
        self.chat = ChatView()
        self.input = InputBar(settings.ptt_key)
        self.input.setEnabled(False)
        self.popups = PopupManager(self)
        self._build_layout()

        self._connect()
        self.apply_color(self.base, save=False)
        self.show_state(AssistantState.LOADING)

    def _build_layout(self) -> None:
        shell = QWidget(objectName="Shell")
        shell.setAttribute(Qt.WA_StyledBackground)
        # Contenu limité en largeur et centré : reste lisible même en plein écran.
        content = QWidget()
        content.setMaximumWidth(MAX_CONTENT_WIDTH)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 0, 18, 18)
        layout.setSpacing(4)
        layout.addWidget(self.orb)
        layout.addWidget(self.status)
        layout.addWidget(self.info)
        layout.addSpacing(6)
        layout.addWidget(self.chat, 1)
        layout.addSpacing(8)
        layout.addWidget(self.input)
        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(content, 100)
        centered.addStretch(1)
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.title_bar)
        outer.addLayout(centered, 1)
        self.frame = ResizableFrame(shell)
        self.setCentralWidget(self.frame)

    def _connect(self) -> None:
        b, a = self.bridge, self.assistant
        b.ready.connect(self.on_ready)
        b.state.connect(self.show_state)
        b.user_message.connect(self.chat.add_user)
        b.reply_start.connect(self.chat.start_reply)
        b.reply_chunk.connect(self.chat.append_reply)
        b.reply_end.connect(self.chat.end_reply)
        b.notice.connect(self.chat.add_notice)
        b.tool.connect(self.chat.add_tool)
        b.display.connect(self.popups.show)
        b.confirmation.connect(
            lambda question: self.chat.add_confirmation(question).answered.connect(
                self.assistant.answer_confirmation
            )
        )
        b.memory.connect(lambda text: self.chat.add_notice(f"🧠 Mémorisé : {text}", "MemoryNotice"))
        b.mic_level.connect(self.orb.set_mic_level)
        b.speech_audio.connect(self.orb.play_speech)

        self.input.submitted.connect(a.submit_text)
        self.input.mic_pressed.connect(a.start_listening)
        self.input.mic_released.connect(a.stop_listening)
        self.input.voice_toggled.connect(lambda: self.input.set_voice(a.toggle_voice()))
        self.input.reset_clicked.connect(self._reset)
        self.title_bar.color_menu.color_chosen.connect(self.apply_color)

    def apply_color(self, base: QColor, save: bool = True) -> None:
        """Change la couleur de toute l'interface, à chaud (pop-ups ouverts compris)."""
        self.base = QColor(base)
        palette = theme.apply_theme(QApplication.instance(), self.base)
        self.title_bar.refresh(palette)
        self.input.refresh(palette)
        self.orb.set_base_color(self.base)
        self.show_state(self.state)
        if save:
            preferences.save({"color": self.base.name()}, self._preferences_path)

    def on_ready(self, info: str) -> None:
        self.info.setText(info)
        self.input.setEnabled(True)
        self.input.mic.setEnabled(self.assistant.can_listen)
        self.input.set_voice(self.assistant.voice_on)
        self.input.edit.setFocus()

    def show_state(self, state: AssistantState) -> None:
        self.state = state
        self.orb.set_state(state)
        self.status.setText(state.value.upper())
        self.status.setStyleSheet(f"color: {theme.current().states[state]};")

    def _reset(self) -> None:
        self.chat.clear()
        self.assistant.reset()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.WindowStateChange:  # plein écran : plus de marge ni de poignée
            self.frame.set_maximized(self.isMaximized())
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        self.popups.close_all()
        self.assistant.shutdown()
        super().closeEvent(event)
