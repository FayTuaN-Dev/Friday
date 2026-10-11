import tempfile
from pathlib import Path

import numpy as np
from fakes import SETTINGS
from PySide6.QtWidgets import QApplication

from friday.app.events import AssistantState
from friday.ui.desktop.widgets.holo import speech_envelope

app = QApplication.instance() or QApplication([])


class StubGate:
    opened = False

    def ready(self):
        self.opened = True


class StubAssistant:
    can_listen = True
    voice_on = True

    def __init__(self):
        self.sent = []
        self.scene_gate = StubGate()

    def submit_text(self, text):
        self.sent.append(text)

    def start_listening(self): ...
    def stop_listening(self): ...
    def toggle_voice(self):
        return False

    def reset(self): ...
    def answer_confirmation(self, approved): ...

    def attach_file(self, path):
        self.attached = path

    def shutdown(self): ...


def make_window(tmp_path=None):
    from friday.ui.desktop.main_window import MainWindow

    prefs = (tmp_path or Path(tempfile.mkdtemp())) / "interface.json"
    return MainWindow(SETTINGS, assistant=StubAssistant(), preferences_path=prefs)


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
    w.input.edit.setText("  Salut Friday  ")
    w.input.edit.returnPressed.emit()
    assert w.assistant.sent == ["Salut Friday"]
    assert w.input.edit.text() == ""
    w.input.voice.click()
    assert w.input._voice_on is False  # icône « muet »
    w.close()


def test_speech_envelope():
    env = speech_envelope(np.ones(16000, dtype=np.float32) * 0.1, 16000)
    assert env.size == 60  # une valeur par image, à 60 images par seconde
    assert 0 < env.max() <= 1


def test_popups_open_beside_window_and_are_limited():
    from friday.tools.base import Display
    from friday.ui.desktop.popups.manager import MAX_OPEN

    w = make_window()
    w.show()
    result = {"title": "Météo <Lyon>", "url": "https://meteo.fr", "snippet": "18°C"}
    image = {"title": "x", "data": b"pas une image", "url": "u", "image": "i"}
    displays = [
        Display("results", "Recherche : météo", {"results": [result]}),
        Display("article", "Article", {"url": "https://ex.fr/a", "text": "Bonjour " * 50}),
        Display("images", "chats", {"images": [image]}),
        Display("results", "Recherche : météo", {"results": [result]}),
    ]
    for d in displays:
        w.bridge.on_display(d)
    w.bridge.on_tool("🔎 Recherche : météo")
    app.processEvents()

    assert len(w.popups.popups) == MAX_OPEN  # le plus ancien a été fermé
    assert w.popups.show(Display("inconnu", "?")) is None
    w.close()
    app.processEvents()
    assert w.popups.popups == []


def test_weather_popup_renders():
    from friday.tools.base import Display
    from friday.ui.desktop.popups.weather import WeatherPopup

    now = {"temperature": 18, "feels_like": 20, "label": "couvert", "icon": "☁️", "wind": 7,
           "humidity": 88}  # fmt: skip
    day = {"day": "Demain", "label": "pluie", "icon": "🌧️", "min": 12, "max": 24, "rain": 70}
    popup = WeatherPopup(Display("weather", "Bordeaux (France)", {"current": now, "days": [day]}))
    popup.show()
    app.processEvents()
    popup.close()


def test_confirmation_card_and_claude_popup():
    from friday.tools.base import Display
    from friday.ui.desktop.popups.claude import ClaudePopup

    w = make_window()
    answers = []
    w.bridge.on_confirmation("Je confie à Claude : écrire a.py. Je lance ?")
    app.processEvents()
    card = w.chat._cards[0]
    card.answered.connect(answers.append)
    card.yes.click()
    assert answers == [True] and not card.yes.isEnabled()
    w.close()

    data = {"ok": True, "result": "# Fait\n```python\nprint(1)\n```", "files": ["a.py"],
            "seconds": 75, "workspace": "."}  # fmt: skip
    popup = ClaudePopup(Display("claude", "Écrire a.py", data))
    popup.show()
    app.processEvents()
    popup.close()


def test_color_choice_recolors_interface_and_is_remembered(tmp_path):
    from PySide6.QtGui import QColor

    from friday.ui.desktop import preferences, theme

    w = make_window(tmp_path)
    w.show_state(AssistantState.LISTENING)
    w.apply_color(QColor("#3cc8ff"))
    assert theme.current().base.name() == "#3cc8ff"
    assert w.orb.base.name() == "#3cc8ff"
    assert theme.current().states[AssistantState.LISTENING] in w.status.styleSheet()
    assert preferences.load(tmp_path / "interface.json") == {"color": "#3cc8ff"}
    w.close()

    again = make_window(tmp_path)  # la couleur choisie revient au lancement suivant
    assert again.base.name() == "#3cc8ff"
    again.close()


def test_holo_orb_draws_every_state():
    from friday.ui.desktop.widgets.holo import HoloOrb

    orb = HoloOrb()
    orb.resize(400, 280)
    for state in AssistantState:
        orb.set_state(state)
        for _ in range(5):
            orb._tick()
        orb.grab()  # dessine sans planter, même sans fenêtre visible
    orb.play_speech(np.ones(8000, dtype=np.float32) * 0.2, 16000)
    orb._tick()
    assert 0 <= orb.level <= 1.2


def test_dropped_file_is_attached(tmp_path):
    from PySide6.QtCore import QMimeData, QUrl

    from friday.ui.desktop.main_window import dropped_files

    path = tmp_path / "devis.pdf"
    path.write_bytes(b"%PDF")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)), QUrl.fromLocalFile(str(tmp_path)),
                  QUrl("https://exemple.fr")])  # fmt: skip
    assert dropped_files(mime) == [path]  # ni dossier, ni lien web


def test_friday_bubbles_render_markdown():
    from PySide6.QtCore import Qt

    from friday.ui.desktop.widgets.chat import Bubble

    assert Bubble("Friday", "**ticket.pdf**", from_user=False).label.textFormat() == Qt.MarkdownText
    assert Bubble("Vous", "**pas touché**", from_user=True).label.textFormat() != Qt.MarkdownText


def test_friday_can_close_her_popups():
    from friday.tools.base import Display
    from friday.tools.popups import ClosePopupsTool

    w = make_window()
    result = {"title": "t", "url": "https://ex.fr", "snippet": "s"}
    for _ in range(2):
        w.bridge.on_display(Display("results", "Recherche", {"results": [result]}))
    app.processEvents()
    w.bridge.on_display(ClosePopupsTool().run("last").display)
    app.processEvents()
    assert len(w.popups.popups) == 1
    w.bridge.on_display(ClosePopupsTool().run().display)
    app.processEvents()
    assert w.popups.popups == []
    w.close()


def test_the_core_shrinks_during_a_conversation():
    """U1 : la place va au chat dès le premier message ; « Nouvelle conversation » la rend."""
    from PySide6.QtTest import QTest

    from friday.ui.desktop.stage import STAGE_COMPACT, STAGE_FULL

    w = make_window()
    w.bridge.on_ready("Cerveau : qwen3:8b")
    app.processEvents()
    assert not w.compact and w.stage.height() == STAGE_FULL
    assert not hasattr(w.title_bar, "color_button")  # la couleur : dans les réglages
    w.bridge.on_user_message("Bonjour", True)
    QTest.qWait(600)
    assert w.compact and w.stage.height() == STAGE_COMPACT and w.info.isHidden()
    w._reset()
    QTest.qWait(600)
    assert not w.compact and w.stage.height() == STAGE_FULL and not w.info.isHidden()
    w.close()


def test_the_core_regrows_after_a_quiet_minute(monkeypatch):
    """Une minute de veille : le cœur reprend sa taille (la conversation reste) ; il se
    réduit de nouveau au message suivant ; toute activité annule l'attente."""
    from PySide6.QtTest import QTest

    from friday.ui.desktop import stage

    monkeypatch.setattr(stage, "REGROW_MS", 100)
    w = make_window()
    w.bridge.on_ready("")
    w.bridge.on_user_message("Bonjour", True)
    w.bridge.on_state(AssistantState.SPEAKING)
    QTest.qWait(250)
    assert w.compact  # elle parle : on n'attend pas
    w.bridge.on_state(AssistantState.IDLE)
    w.bridge.on_state(AssistantState.LISTENING)  # activité : attente annulée
    QTest.qWait(250)
    assert w.compact
    w.bridge.on_state(AssistantState.IDLE)
    QTest.qWait(800)
    assert not w.compact and w.chat._bubbles  # grand, conversation gardée
    w.bridge.on_user_message("Et demain ?", True)
    QTest.qWait(600)
    assert w.compact
    w.close()
