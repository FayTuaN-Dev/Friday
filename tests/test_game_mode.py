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
from friday.brain.gpu_gate import GatedClient, unload_all


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


class FakeSTT:
    def __init__(self):
        self.loaded = True

    def unload(self):
        self.loaded = False

    def reload(self):
        self.loaded = True


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
    brain = SimpleNamespace(client=None, warmup=lambda: warmed.append(gpu_gate.OPEN.is_set()))
    listener = RecordingListener()
    states = []
    assistant = SimpleNamespace(
        settings=SimpleNamespace(user_name="Monsieur"), listener=listener, voice_on=False,
        components=SimpleNamespace(brain=brain, stt=FakeSTT(), speaker=None),
        set_state=states.append,
    )  # fmt: skip
    game = GameMode(assistant)
    assert game.command("Friday, mode jeu")
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
