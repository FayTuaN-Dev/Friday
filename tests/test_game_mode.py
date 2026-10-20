import threading
import time
from types import SimpleNamespace

import numpy as np
import ollama
import pytest
from fakes import RecordingListener

from friday.app import game_mode
from friday.app.events import AssistantState
from friday.app.game_mode import GameMode, asks_game_mode, asks_return
from friday.brain import gpu_gate
from friday.brain.gpu_gate import GatedClient, unload_all, unload_mine


@pytest.fixture(autouse=True)
def gate_open_after_test():
    yield
    gpu_gate.OPEN.set()  # jamais une barrière fermée pour les tests suivants


def test_game_mode_is_asked_in_words():
    for text in ("Friday, mode jeu", "passe en mode gaming", "je vais jouer, à plus"):
        assert asks_game_mode(text), text
    for text in ("fin du mode jeu", "quel jeu me conseilles-tu ?", "quitte le mode jeu"):
        assert not asks_game_mode(text), text


def test_return_is_recognised_even_with_a_mangled_name():
    # transcriptions réelles de la petite oreille (Whisper tiny)
    for text in ("Friday, reviens.", "Faye des reviens.", "Froidé, tu peux revenir.",
                 "Friday revient", "Friday, réveille-toi"):  # fmt: skip
        assert asks_return(text), text
    for text in ("Il est tout le fusil.", "Bon, on lance la partie.", "Il revient quand ?"):
        assert not asks_return(text), text


def test_closed_gate_holds_ollama_calls_until_the_game_ends(monkeypatch):
    calls = []
    monkeypatch.setattr(ollama.Client, "chat", lambda self, *a, **k: calls.append("chat"))
    gpu_gate.OPEN.clear()
    worker = threading.Thread(target=lambda: GatedClient().chat(model="qwen3:8b"))
    worker.start()
    time.sleep(0.2)
    assert calls == []  # attend : aucun modèle rechargé en pleine partie
    gpu_gate.OPEN.set()
    worker.join(2)
    assert calls == ["chat"]


class FakeOllama:
    def __init__(self, models):
        self.models = list(models)

    def ps(self):
        return SimpleNamespace(models=[SimpleNamespace(model=m) for m in self.models])


def test_unload_passes_the_closed_gate(monkeypatch):
    client = FakeOllama(["qwen3:8b", "embeddinggemma:latest"])

    def generate(self, model, keep_alive):
        assert keep_alive == 0
        self.models.remove(model)

    monkeypatch.setattr(ollama.Client, "generate", generate)
    gpu_gate.OPEN.clear()
    assert unload_all(client) == ["qwen3:8b", "embeddinggemma:latest"]
    assert client.models == []


def test_quitting_friday_frees_only_its_own_models(monkeypatch):
    client = FakeOllama(["qwen3:8b", "embeddinggemma:latest", "llama3:8b"])  # llama : un autre
    monkeypatch.setattr(ollama.Client, "generate", lambda self, model, keep_alive:
                        self.models.remove(model))  # fmt: skip
    assert unload_mine(client, ("qwen3:8b", "", "embeddinggemma")) == [
        "qwen3:8b", "embeddinggemma:latest"]  # fmt: skip
    assert client.models == ["llama3:8b"]


class FakeSTT:
    def __init__(self, order):
        self.loaded = True
        self.order = order

    def unload(self):
        self.loaded = False

    def reload(self):
        self.loaded = True
        self.order.append("whisper")


class FakeEar:
    def __init__(self, models_dir):
        pass

    def transcribe(self, audio):
        return "Faye des reviens."


def paused_friday(monkeypatch):
    monkeypatch.setattr(game_mode, "PauseEar", FakeEar)
    monkeypatch.setattr(game_mode, "vram_used_mb", lambda: 900)
    monkeypatch.setattr(gpu_gate, "unload_all", lambda client: ["qwen3:8b"])
    warmed = []

    def warmup():
        warmed.append(gpu_gate.OPEN.is_set())
        order.append("qwen")

    order = []
    embeds = SimpleNamespace(embed=lambda **k: order.append("mémoire"))
    brain = SimpleNamespace(client=embeds, warmup=warmup)
    listener = RecordingListener()
    states = []
    assistant = SimpleNamespace(
        settings=SimpleNamespace(user_name="Monsieur", memory_enabled=True, embed_model="e"),
        listener=listener, voice_on=False,
        components=SimpleNamespace(brain=brain, stt=FakeSTT(order), speaker=None),
        set_state=states.append,
    )  # fmt: skip
    game = GameMode(assistant)
    assert game.command("Friday, mode jeu")
    game.order = order
    return game, assistant, states, warmed


def test_pause_frees_the_gpu_and_the_return_reloads_everything(monkeypatch):
    game, assistant, states, warmed = paused_friday(monkeypatch)
    assert game.paused and not gpu_gate.OPEN.is_set()
    assert not assistant.components.stt.loaded
    assert states == [AssistantState.PAUSED]
    assert assistant.listener.of("display") == [("game_mode",)]

    game.heard("Il est tout le fusil.")  # la partie continue
    assert game.paused
    game.heard(game.transcribe(np.zeros(16000, dtype=np.float32)))  # « Faye des reviens »
    for _ in range(50):
        if not game.paused:
            break
        time.sleep(0.02)
    assert not game.paused and gpu_gate.OPEN.is_set()
    assert assistant.components.stt.loaded and warmed == [True]  # rechargé, barrière ouverte
    # l'ordre du démarrage : Whisper d'abord faisait déborder qwen (200 jetons/s au lieu de 1 550)
    assert game.order == ["mémoire", "qwen", "whisper"]
    assert states[-2:] == [AssistantState.LOADING, AssistantState.IDLE]


def test_the_pause_ear_ignores_long_chatter():
    ear = game_mode.PauseEar.__new__(game_mode.PauseEar)
    ear.model = None  # ne doit même pas être appelé
    assert ear.transcribe(np.zeros(16000 * 6, dtype=np.float32)) == ""


def test_unloaded_whisper_transcribes_nothing():
    from friday.voice.stt import WhisperSTT

    stt = WhisperSTT.__new__(WhisperSTT)
    stt._lock, stt.model = threading.Lock(), None
    assert stt.transcribe(np.ones(16000, dtype=np.float32)) == "" and not stt.loaded


def test_return_summary_counts_what_happened_during_the_game(monkeypatch):
    from datetime import datetime, timedelta

    from friday.app.game_summary import GameSummary, length

    clock = [datetime(2026, 10, 14, 20, 0)]
    google = SimpleNamespace(connected=True)
    unread = iter([5, 8])
    monkeypatch.setattr(
        "friday.app.game_summary.unread_mails", lambda g: next(unread) if g else None
    )
    summary = GameSummary(google, clock=lambda: clock[0])
    clock[0] += timedelta(minutes=85)
    text = summary.text(["rappel", "rappel", "analyse"])
    assert text == ("Me revoilà. Pendant votre partie (1 h 25) : 2 rappels, 1 tâche terminée "
                    "et 3 nouveaux mails.")  # fmt: skip
    assert GameSummary(None).text([]) == "Me revoilà."
    assert length(45) == "45 min" and length(120) == "2 h"


def test_background_tasks_wait_for_the_return_with_only_a_notification(monkeypatch):
    game, assistant, states, _ = paused_friday(monkeypatch)
    posted = []
    assistant.post = lambda kind, payload=None: posted.append((kind, payload))
    from friday.tools.base import ToolResult

    reminder = ("rappel", ToolResult("Dis EXACTEMENT : « Rappel : appeler Julie »"))
    assert game.keep_for_later(*reminder)  # pas d'annonce par qwen pendant la partie
    assert assistant.listener.of("display")[-1] == ("notification",)
    game.leave()
    for _ in range(50):
        if posted:
            break
        time.sleep(0.02)
    assert posted == [("done", reminder)]  # annoncé après « Me revoilà »
    assert not game.keep_for_later(*reminder)  # hors mode jeu : annonce normale


def test_tray_and_button_toggle_the_game_mode(monkeypatch):
    game, assistant, _, _ = paused_friday(monkeypatch)
    posted = []
    assistant.post = lambda kind, payload=None: posted.append((kind, payload))
    game.toggle()  # en pause : « Reprendre »
    for _ in range(50):
        if not game.paused:
            break
        time.sleep(0.02)
    assert not game.paused
    game.toggle()  # puis « Mode jeu » : passe par le fil de l'assistant
    assert posted[-1] == ("game", "")


def test_tray_icon_tells_how_to_come_back():
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QWidget
    from test_desktop import app  # noqa: F401  (QApplication)

    from friday.ui.desktop.notifier import Notifier

    notifier = Notifier(QWidget(), QIcon())
    if notifier.tray is None:  # pas de zone de notification (CI)
        return
    notifier.set_game(True)
    assert "reviens" in notifier.tray.toolTip() and "Reprendre" in notifier.game_action.text()
    notifier.set_game(False)
    assert notifier.tray.toolTip() == "Friday"


def test_a_model_that_stays_is_asked_again(monkeypatch):
    """Constaté : qwen encore là 10 s après la demande ; Friday abandonnait sans relancer."""
    client = FakeOllama(["qwen3:8b", "embeddinggemma:latest"])
    asked = []

    def generate(self, model, keep_alive):
        asked.append(model)
        if model != "qwen3:8b" or asked.count(model) == 2:  # qwen ne part qu'au 2e essai
            self.models.remove(model)

    monkeypatch.setattr(ollama.Client, "generate", generate)

    def wait(client, name):
        return name not in client.models

    assert unload_all(client, wait=wait) == ["qwen3:8b", "embeddinggemma:latest"]
    assert client.models == [] and asked == ["qwen3:8b", "embeddinggemma:latest", "qwen3:8b"]
    stuck = FakeOllama(["qwen3:8b"])
    monkeypatch.setattr(ollama.Client, "generate", lambda self, model, keep_alive: None)
    assert unload_all(stuck, attempts=2, wait=wait) == ["qwen3:8b"]  # abandon au bout de 2
