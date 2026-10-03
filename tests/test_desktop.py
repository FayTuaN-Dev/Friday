import numpy as np
from fakes import SETTINGS
from PySide6.QtWidgets import QApplication

from jarvis.app.events import AssistantState
from jarvis.ui.desktop.theme import stylesheet
from jarvis.ui.desktop.widgets.orb import speech_envelope

app = QApplication.instance() or QApplication([])


class StubAssistant:
    can_listen = True
    voice_on = True

    def __init__(self):
        self.sent = []

    def submit_text(self, text):
        self.sent.append(text)

    def start_listening(self): ...
    def stop_listening(self): ...
    def toggle_voice(self):
        return False

    def reset(self): ...
    def shutdown(self): ...


def make_window():
    from jarvis.ui.desktop.main_window import MainWindow

    app.setStyleSheet(stylesheet())
    return MainWindow(SETTINGS, assistant=StubAssistant())


def test_window_reacts_to_assistant_events():
    w = make_window()
    assert not w.input.isEnabled()  # tant que les modèles chargent

    w.bridge.on_ready("Cerveau : qwen3:8b")
    w.bridge.on_state(AssistantState.SPEAKING)
    w.bridge.on_user_message("Bonjour", True)
    w.bridge.on_reply_start()
    w.bridge.on_reply_chunk("Bonjour ")
    w.bridge.on_reply_chunk("Monsieur.")
    w.bridge.on_reply_end(False)
    app.processEvents()

    assert w.input.isEnabled()
    assert w.status.text() == "PARLE"
    assert w.chat._bubbles[-1].label.text() == "Bonjour Monsieur."
    w.orb.repaint()  # le dessin ne doit pas planter
    w.close()


def test_input_bar_sends_text_and_toggles_voice():
    w = make_window()
    w.bridge.on_ready("")
    app.processEvents()
    w.input.edit.setText("  Salut Jarvis  ")
    w.input.edit.returnPressed.emit()
    assert w.assistant.sent == ["Salut Jarvis"]
    assert w.input.edit.text() == ""
    w.input.voice.click()
    assert w.input.voice.text() == "🔇"
    w.close()


def test_speech_envelope():
    env = speech_envelope(np.ones(16000, dtype=np.float32) * 0.1, 16000)
    assert env.size == 60  # une valeur par image, à 60 images par seconde
    assert 0 < env.max() <= 1
