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


def test_slow_voice_and_frozen_window_are_logged(caplog):
    """Pour relier un à-coup ressenti à sa cause : voix fabriquée trop lentement (processeur
    trop pris), interface figée."""
    import logging

    import numpy as np

    from friday.voice.speaker import Speaker

    class SlowTTS:
        sample_rate = 1000

        def synthesize(self, text):
            time.sleep(0.15)  # 0,15 s pour 0,2 s de parole : trop lent
            return np.zeros(200, dtype=np.float32)

    caplog.set_level(logging.WARNING)
    speaker = Speaker(SlowTTS(), play=lambda audio, rate: None, stop_playback=lambda: None)
    speaker.say("Monsieur, la météo.")
    speaker.wait()
    assert "Voix lente" in caplog.text and "pour fabriquer 0.2 s de parole" in caplog.text

    from test_desktop import app  # noqa: F401  (QApplication)

    from friday.ui.desktop.freeze_watch import FreezeWatch

    watch = FreezeWatch()
    watch._last -= 0.6  # 600 ms sans nouvelles : l'interface était figée
    watch._tick()
    assert "Interface figée" in caplog.text and watch.worst > 400


def test_a_freeze_is_photographed_with_every_thread(caplog):
    """Pendant un gel, une minuterie en C photographie TOUS les fils (sans le verrou de
    Python) : où était l'interface, et ce que faisaient les autres pendant ce temps."""
    import logging
    import threading

    from test_desktop import app  # noqa: F401  (QApplication)

    from friday.ui.desktop.freeze_watch import FreezeWatch

    caplog.set_level(logging.WARNING)
    watch = FreezeWatch()
    stop = threading.Event()

    def busy_worker_thread():
        x = 0
        while not stop.is_set():
            x += 1  # un autre fil qui travaille pendant le gel

    worker = threading.Thread(target=busy_worker_thread, name="travailleur")
    worker.start()

    def slow_thing_in_the_window():
        time.sleep(0.7)  # un travail lent dans le fil de l'interface

    try:
        slow_thing_in_the_window()
        watch._tick()
    finally:
        stop.set()
        worker.join()
    assert any("slow_thing_in_the_window" in c for c in watch.culprits)
    assert any(c.startswith("travailleur :") and "busy_worker_thread" in c for c in watch.culprits)
    assert "Gel : l'interface était dans" in caplog.text and "pendant ce temps" in caplog.text
    watch.deleteLater()


def test_python_hands_over_quickly_to_the_interface():
    """Le verrou de Python passe d'un fil à l'autre toutes les 0,5 ms (5 par défaut)."""
    import sys

    from friday.ui.desktop.app import SWITCH_INTERVAL, keep_interface_responsive

    before = sys.getswitchinterval()
    try:
        keep_interface_responsive()
        assert sys.getswitchinterval() == SWITCH_INTERVAL == 0.0005
    finally:
        sys.setswitchinterval(before)
