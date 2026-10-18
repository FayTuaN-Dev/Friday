"""Les cartes « Friday » et « Pi » des colonnes de côté (W2)."""

from types import SimpleNamespace

import httpx
from PySide6.QtWidgets import QApplication

from friday.app.events import AssistantState
from friday.app.friday_status import FridayStatus, Model, Status, loaded_models, pi_status
from friday.ui.desktop.side.friday_cards import FridayCard, PiCard, duration

app = QApplication.instance() or QApplication([])
GB = 1024**3


def test_loaded_models_and_their_share_on_the_gpu():
    client = SimpleNamespace(ps=lambda: SimpleNamespace(models=[
        SimpleNamespace(model="qwen3:8b", size_vram=6 * GB, size=6 * GB),
        SimpleNamespace(model="bge-m3", size_vram=GB, size=2 * GB)]))  # fmt: skip
    models = loaded_models(client)
    assert [(m.name, m.vram, m.on_gpu) for m in models] == [("qwen3:8b", 6.0, 1.0),
                                                              ("bge-m3", 1.0, 0.5)]  # fmt: skip

    def down():
        raise ConnectionError("Ollama arrêté")

    assert loaded_models(SimpleNamespace(ps=down)) is None


def test_pi_status_uses_the_key_and_survives_a_dead_pi():
    seen = {}

    def get(url, headers, timeout):
        seen.update(url=url, auth=headers["Authorization"])
        return SimpleNamespace(status_code=200, json=lambda: {
            "pret": True, "modele": "qwen3:4b", "machine": {"temperature": 51.2}})  # fmt: skip

    assert pi_status("https://pi", "cle", get) == {"modele": "qwen3:4b", "temperature": 51.2}
    assert seen == {"url": "https://pi/api/etat", "auth": "Bearer cle"}

    def dead(*a, **k):
        raise httpx.ConnectError("injoignable")

    assert pi_status("https://pi", "cle", dead) is None
    unset = FridayStatus(SimpleNamespace(ps=lambda: SimpleNamespace(models=[])))
    assert unset.read() == Status([], None, False)  # Pi pas réglé : jamais appelé


def test_friday_card_shows_state_models_and_spill():
    clicks = []
    card = FridayCard(lambda: clicks.append(1), "small (carte graphique)")
    card.set_state(AssistantState.PAUSED)
    assert card.state.text() == "Mode jeu" and card.game.text() == "Revenir"
    card.game.click()
    assert clicks == [1]
    card.show_status(Status([Model("qwen3:8b", 5.2, 5.2), Model("bge-m3", 0.6, 1.2)]))
    assert card.models[0].name.text() == "QWEN3:8B" and card.models[0].value.text() == "5,2 Go"
    assert not card.models[0].value.property("alert")
    assert card.models[1].value.property("alert")  # moitié sur le processeur
    assert "50 % sur le processeur" in card.models[1].detail.text()
    assert card.note.text() == "Écoute : Whisper small (carte graphique)"
    card.show_status(Status(None))
    assert "Ollama ne répond pas." in card.note.text()
    assert not card.models[0].value.isVisibleTo(card)


def test_pi_card_online_and_offline():
    card = PiCard(clock=lambda: 10_000.0)
    card.show_status(Status([], {"temperature": 52.0, "memory_used": 1.9, "memory_total": 7.6,
                                 "uptime": 3 * 86400 + 4 * 3600, "last_message": 10_000 - 720},
                            True))  # fmt: skip
    assert card.online.text() == "EN LIGNE" and card.temperature.value.text() == "52 °C"
    assert card.memory.detail.text() == "1,9 / 8 Go"
    assert card.detail.text() == "Allumé depuis 3 j 4 h · dernière question il y a 12 min"
    card.show_status(Status([], None, True))
    assert card.online.text() == "HORS LIGNE" and card.online.property("alert")
    assert not card.temperature.value.isVisibleTo(card)
    assert duration(30) == "1 min" and duration(3 * 3600 + 300) == "3 h 05"


def test_pi_card_appears_only_once_the_pi_is_configured():
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget
    from test_side_widgets import FakeSampler

    from friday.ui.desktop.side.columns import SidePanels

    playing, limits = QFrame(), QFrame()
    playing.has_track = False
    status = FakeSampler()
    side = SidePanels(playing, limits, {}, FakeSampler(), status)
    window = QWidget()
    row = QHBoxLayout(window)
    row.addWidget(side.left)
    row.addWidget(side.right)
    window.show()
    side.place(True)
    assert side.cards["friday"].isVisible() and not side.cards["pi"].isVisible()
    assert status.requests == 1  # on ne sait pas encore si le Pi est réglé
    status.read.emit(Status([], {"temperature": 50.0}, True))
    assert side.cards["pi"].isVisible()
    window.close()
