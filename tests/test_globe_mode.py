import time
from types import SimpleNamespace

import ollama
import pytest
from fakes import RecordingListener

from friday.app import globe_mode
from friday.app.globe_mode import GlobeMode, asks_globe, asks_globe_closed
from friday.brain import gpu_gate
from friday.brain.gpu_gate import GatedClient

SMALL = "qwen3:4b-instruct-2507-q4_K_M"


@pytest.fixture(autouse=True)
def clean_gate():
    yield
    gpu_gate.OPEN.set()
    gpu_gate.STAND_IN.clear()
    gpu_gate.NO_THINK.clear()


def test_the_globe_is_asked_in_words():
    for text in ("Friday, ouvre l'œil de Dieu", "lance God's Eye", "mode globe",
                 "montre-moi l'oeil de dieu"):  # fmt: skip
        assert asks_globe(text), text
    for text in ("ferme l'œil de Dieu", "affiche le globe", "montre-moi le monde"):
        assert not asks_globe(text), text  # le globe de Friday reste le sien
    for text in ("ferme l'œil de Dieu", "Friday, ferme le globe", "quitte God's Eye"):
        assert asks_globe_closed(text), text
    assert not asks_globe_closed("ferme Spotify")


def test_every_ollama_call_uses_the_stand_in(monkeypatch):
    seen = []
    monkeypatch.setattr(ollama.Client, "chat", lambda self, *a, **k: seen.append(k))
    gpu_gate.STAND_IN["qwen3:8b"] = SMALL
    gpu_gate.NO_THINK.add(SMALL)
    GatedClient().chat(model="qwen3:8b", think=True, messages=[])  # réponse, tri, mémoire…
    GatedClient().chat(model="qwen3-vl:4b-instruct", think=False)  # la vision n'est pas touchée
    assert seen[0]["model"] == SMALL and "think" not in seen[0]  # le 4b ne réfléchit pas
    assert seen[1] == {"model": "qwen3-vl:4b-instruct", "think": False}


class FakeApp:
    def __init__(self):
        self.installed, self.window, self.closed = True, False, 0
        self.folder = SimpleNamespace(parent="C:/Dev")

    def start(self):
        return True

    def open_window(self):
        self.window = True
        return True

    def window_open(self):
        return self.window

    def close(self):
        self.closed += 1
        self.window = False


def friday_with_globe(monkeypatch, thinks=False):
    monkeypatch.setattr(gpu_gate, "unload_all", lambda client: ["qwen3:8b"])
    monkeypatch.setattr(globe_mode, "WATCH_EVERY", 0.05)
    monkeypatch.setattr(globe_mode, "GRACE", 0.1)
    loaded = []
    client = SimpleNamespace(
        show=lambda model: SimpleNamespace(capabilities=["tools"] + ["thinking"] * thinks),
        embed=lambda **k: None,
    )
    brain = SimpleNamespace(client=client, warmup=lambda: loaded.append(
        gpu_gate.STAND_IN.get("qwen3:8b", "qwen3:8b")))  # fmt: skip
    stt = SimpleNamespace(unload=lambda: loaded.append("-whisper"),
                          reload=lambda: loaded.append("whisper"))  # fmt: skip
    posted, states = [], []
    assistant = SimpleNamespace(
        settings=SimpleNamespace(ollama_model="qwen3:8b", globe_model=SMALL, globe_dir="",
                                 memory_enabled=False),
        listener=RecordingListener(), voice_on=False, set_state=states.append,
        components=SimpleNamespace(brain=brain, stt=stt, speaker=None),
        game=SimpleNamespace(paused=False), post=lambda kind, what: posted.append((kind, what)),
    )  # fmt: skip
    app = FakeApp()
    return GlobeMode(assistant, app), app, loaded, posted


def test_the_small_brain_takes_over_while_the_globe_is_open(monkeypatch):
    globe, app, loaded, posted = friday_with_globe(monkeypatch)
    assert globe.command("Friday, ouvre l'œil de Dieu")
    assert globe.on and app.window
    assert gpu_gate.STAND_IN == {"qwen3:8b": SMALL} and SMALL in gpu_gate.NO_THINK
    assert loaded == ["-whisper", SMALL, "whisper"]  # le modèle d'abord, l'écoute ensuite
    assert globe.command("Friday, ferme l'œil de Dieu")
    assert not globe.on and app.closed == 1 and gpu_gate.STAND_IN == {}
    assert loaded[-3:] == ["-whisper", "qwen3:8b", "whisper"]  # le cerveau habituel revient


def test_closing_the_window_brings_the_usual_brain_back(monkeypatch):
    globe, app, loaded, posted = friday_with_globe(monkeypatch)
    globe.enter()
    app.window = False  # l'utilisateur ferme la fenêtre du globe
    for _ in range(100):
        if posted:
            break
        time.sleep(0.02)
    assert posted == [("globe", "closed")]
    globe.event("closed")
    assert not globe.on and gpu_gate.STAND_IN == {}


def test_a_missing_small_model_is_said_without_touching_anything(monkeypatch):
    globe, app, loaded, posted = friday_with_globe(monkeypatch)

    def missing(model):
        raise ollama.ResponseError("not found", 404)

    globe.assistant.components.brain.client.show = missing
    globe.enter()
    assert not globe.on and loaded == [] and gpu_gate.STAND_IN == {}
    said = [e[1] for e in globe.assistant.listener.events if e[0] == "chunk"]
    assert "ollama pull" in said[-1]


def test_the_globe_window_is_recognised_by_its_own_profile(monkeypatch, tmp_path):
    from friday.app import globe_app

    profile = tmp_path / "globe-navigateur"
    procs = [
        SimpleNamespace(info={"name": "chrome.exe", "cmdline": ["chrome.exe", "--type=gpu"]}),
        SimpleNamespace(info={"name": "chrome.exe",
                              "cmdline": ["chrome.exe", f"--user-data-dir={profile}"]}),
    ]  # fmt: skip
    monkeypatch.setattr(globe_app.psutil, "process_iter", lambda attrs: list(procs))
    app = globe_app.GlobeApp(tmp_path, profile)
    assert app.window_open()  # le Chrome habituel de l'utilisateur ne compte pas
    procs.pop()
    assert not app.window_open()


def test_the_tray_says_friday_runs_on_her_small_brain():
    from test_desktop import make_window

    w = make_window()
    assert w.title_bar.globe_button.toolTip().startswith("Œil de Dieu")
    if w.notifier.tray is None:
        return
    w.notifier.set_globe(True)
    assert "œil de Dieu" in w.notifier.tray.toolTip()
    assert w.notifier.globe_action.text().endswith("Fermer l'œil de Dieu")
    w.notifier.set_globe(False)
    assert w.notifier.tray.toolTip() == "Friday"
