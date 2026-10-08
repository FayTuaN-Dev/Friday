"""Mot d'activation dédié (F2) : détection sur trames de 80 ms, porte devant Whisper, relances
toujours possibles sans le nom ; sans modèle, l'écoute reste celle d'avant."""

import queue
from types import SimpleNamespace

import numpy as np

from friday.app.diagnostic import OK, WARN, _wake
from friday.voice.wakeword import FRAME, WakeWordDetector


class Model:
    """Répond 0,9 aux trames « fortes » (le mot), 0 aux autres."""

    def __init__(self):
        self.frames = 0

    def predict(self, frame):
        self.frames += 1
        return {"friday": 0.9 if np.abs(frame).max() > 20000 else 0.0}


def test_detector_scores_80_ms_frames_and_remembers_when():
    clock = [10.0]
    detector = WakeWordDetector(Model(), 0.5, clock=lambda: clock[0], background=False)
    detector.feed(np.zeros(FRAME * 3 // 2, dtype=np.float32))  # 1,5 trame : le reste attend
    assert detector.model.frames == 1 and not detector.heard_since(0)
    clock[0] = 12.0
    detector.feed(np.full(FRAME, 0.9, dtype=np.float32))  # le mot
    assert detector.heard_since(11.0) and not detector.heard_since(12.5)
    assert detector.best == 0.9


def listener(gate):
    from friday.voice.hands_free import HandsFreeListener

    heard = []
    fake = HandsFreeListener.__new__(HandsFreeListener)
    fake._transcribe, fake._heard_log = (lambda segment: "quelle heure est-il"), None
    fake._on_heard, fake.gate = (lambda text, at: heard.append((text, at))), gate
    fake._segments = queue.Queue()
    return fake, heard


def test_only_awaited_sentences_reach_whisper():
    fake, heard = listener(lambda at: at >= 5)
    for item in ((np.zeros(10), 1.0), (np.zeros(10), 6.0), None):
        fake._segments.put(item)
    fake._transcribe_loop()
    assert heard == [("quelle heure est-il", 6.0)]  # la phrase de 1,0 s : jamais transcrite
    fake, heard = listener(None)  # sans modèle : toutes, comme avant
    fake._segments.put((np.zeros(10), 1.0))
    fake._segments.put(None)
    fake._transcribe_loop()
    assert len(heard) == 1


def test_follow_ups_confirmations_and_stop_need_no_name():
    from friday.app.wake_control import WakeControl

    target = SimpleNamespace(awaiting_confirmation=False, spoke_recently=lambda at: at > 100)
    clock = [0.0]
    wake = WakeControl(target, ["friday"], 8.0, clock=lambda: clock[0])
    assert not wake.expects_speech(50)
    wake.open_follow_up()
    assert wake.expects_speech(5) and not wake.expects_speech(9)  # relance : 8 s
    assert wake.expects_speech(150)  # Friday parle : « stop » suffit
    target.awaiting_confirmation = True
    assert wake.expects_speech(50)  # « Je lance ? » : « oui » suffit


def test_diagnostic_shows_the_wake_word_state(tmp_path):
    settings = SimpleNamespace(wake_threshold=0.6)
    assert _wake(tmp_path, None, settings)[0][1] == WARN
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "friday.onnx").write_bytes(b"onnx")
    line = _wake(tmp_path, SimpleNamespace(wake_detector=object()), settings)[0]
    assert line == ("Mot d'activation", OK, "modèle « Friday » installé, exigence 0,6")


def test_without_the_model_listening_stays_as_before(tmp_path, monkeypatch):
    import friday.core.config as config
    from friday.app.voice_inputs import VoiceInputs

    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    inputs = VoiceInputs.__new__(VoiceInputs)
    assert inputs._wake_word() == (None, None)
