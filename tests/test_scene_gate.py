"""U8 : la voix attend que la scène soit affichée (constaté : la météo, la carte ou le globe se
mettaient en place pendant que Friday parlait déjà, tout à-coups)."""

import threading
import time
from types import SimpleNamespace

from friday.app import scene_gate
from friday.app.reply import Reply
from friday.app.scene_gate import SceneGate
from friday.brain.events import ToolFinished
from friday.tools.base import Display, ToolResult


class Listener:
    def __getattr__(self, name):
        return lambda *args: None


class Speaker:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append((time.monotonic(), text))

    def wait(self): ...


def test_the_voice_waits_for_the_scene(monkeypatch):
    gate, speaker = SceneGate({"place", "world"}), Speaker()
    reply = Reply(Listener(), speaker, threading.Event(), scene_gate=gate)
    shown = Display("world", "Le monde", {"points": []})
    events = [ToolFinished("show_world", ToolResult("…", shown)), "Voici le monde. "]
    opened_at = []

    def open_later():
        time.sleep(0.3)
        opened_at.append(time.monotonic())
        gate.ready()  # l'interface : le voile est tombé

    threading.Thread(target=open_later).start()
    reply.run(iter(events))
    assert speaker.said[0][1] == "Voici le monde." and speaker.said[0][0] >= opened_at[0]


def test_other_displays_and_a_missing_scene_never_block(monkeypatch):
    monkeypatch.setattr(scene_gate, "WAIT", 0.2)
    gate = SceneGate({"place"})
    gate.expect(SimpleNamespace(kind="items"))  # un pop-up : rien à attendre
    start = time.monotonic()
    gate.wait()
    assert time.monotonic() - start < 0.05
    gate.expect(SimpleNamespace(kind="place"))  # la scène ne vient jamais : délai maximal
    gate.wait()
    gate.wait()  # puis plus d'attente pour les phrases suivantes
    assert 0.15 < time.monotonic() - start < 0.4
