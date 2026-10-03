"""Pont entre l'assistant (threads de travail) et Qt (thread de l'interface).

Qt interdit de toucher aux widgets depuis un autre thread : on passe donc par des
signaux, que Qt met en file et délivre dans le thread de l'interface.
"""

import numpy as np
from PySide6.QtCore import QObject, Signal

from jarvis.app.events import AssistantState
from jarvis.tools.base import Display


class QtBridge(QObject):
    ready = Signal(str)
    state = Signal(object)
    user_message = Signal(str, bool)
    reply_start = Signal()
    reply_chunk = Signal(str)
    reply_end = Signal(bool)
    notice = Signal(str)
    tool = Signal(str)
    display = Signal(object)
    mic_level = Signal(float)
    speech_audio = Signal(object, int)

    # Implémentation de AssistantListener

    def on_ready(self, info: str) -> None:
        self.ready.emit(info)

    def on_state(self, state: AssistantState) -> None:
        self.state.emit(state)

    def on_user_message(self, text: str, by_voice: bool) -> None:
        self.user_message.emit(text, by_voice)

    def on_reply_start(self) -> None:
        self.reply_start.emit()

    def on_reply_chunk(self, text: str) -> None:
        self.reply_chunk.emit(text)

    def on_reply_end(self, interrupted: bool) -> None:
        self.reply_end.emit(interrupted)

    def on_notice(self, text: str) -> None:
        self.notice.emit(text)

    def on_tool(self, label: str) -> None:
        self.tool.emit(label)

    def on_display(self, display: Display) -> None:
        self.display.emit(display)

    def on_mic_level(self, level: float) -> None:
        self.mic_level.emit(level)

    def on_speech_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        self.speech_audio.emit(audio, sample_rate)
