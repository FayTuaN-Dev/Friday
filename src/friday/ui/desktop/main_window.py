"""Fenêtre principale : en-tête, cercle HUD, fil de discussion, barre de saisie."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from friday.app.assistant import Assistant
from friday.app.events import AssistantState
from friday.core.config import Settings
from friday.ui.desktop import theme
from friday.ui.desktop.bridge import QtBridge
from friday.ui.desktop.popups.manager import PopupManager
from friday.ui.desktop.widgets.chat import ChatView
from friday.ui.desktop.widgets.input_bar import InputBar
from friday.ui.desktop.widgets.orb import HudOrb

MAX_CONTENT_WIDTH = 820


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, assistant: Assistant | None = None) -> None:
        super().__init__()
        self.setWindowTitle("F.R.I.D.A.Y.")
        self.resize(520, 840)
        self.setMinimumSize(420, 600)

        self.bridge = QtBridge()
        self.assistant = assistant or Assistant(settings, self.bridge)

        self.title = QLabel("F.R.I.D.A.Y.", objectName="Title", alignment=Qt.AlignCenter)
        self.status = QLabel(objectName="Status", alignment=Qt.AlignCenter)
        self.info = QLabel(objectName="Info", alignment=Qt.AlignCenter, wordWrap=True)
        self.orb = HudOrb()
        self.orb.setFixedHeight(250)
        self.chat = ChatView()
        self.input = InputBar(settings.ptt_key)
        self.input.setEnabled(False)
        self.popups = PopupManager(self)

        # Contenu limité en largeur et centré : reste lisible même en plein écran.
        content = QWidget()
        content.setMaximumWidth(MAX_CONTENT_WIDTH)
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        outer.addWidget(content, 100)
        outer.addStretch(1)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(6)
        layout.addWidget(self.title)
        layout.addWidget(self.orb)
        layout.addWidget(self.status)
        layout.addWidget(self.info)
        layout.addWidget(self.chat, 1)
        layout.addWidget(self.input)
        self.setCentralWidget(central)

        self._connect()
        self.show_state(AssistantState.LOADING)

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

    def on_ready(self, info: str) -> None:
        self.info.setText(info)
        self.input.setEnabled(True)
        self.input.mic.setEnabled(self.assistant.can_listen)
        self.input.set_voice(self.assistant.voice_on)
        self.input.edit.setFocus()

    def show_state(self, state: AssistantState) -> None:
        self.orb.set_state(state)
        color = theme.STATE_COLORS[state]
        self.status.setText(state.value.upper())
        self.status.setStyleSheet(f"color: {color};")

    def _reset(self) -> None:
        self.chat.clear()
        self.assistant.reset()

    def closeEvent(self, event) -> None:
        self.popups.close_all()
        self.assistant.shutdown()
        super().closeEvent(event)
