import numpy as np

from jarvis.core.config import _device
from jarvis.voice import ptt
from jarvis.voice.recorder import resample
from jarvis.voice.stt import clean_transcript


def test_resample_to_16k():
    audio = np.ones(48_000, dtype=np.float32)
    out = resample(audio, 48_000)
    assert out.size == 16_000
    assert out.dtype == np.float32


def test_clean_transcript_drops_whisper_hallucinations():
    assert clean_transcript("  Quelle heure est-il ? ") == "Quelle heure est-il ?"
    assert clean_transcript("Sous-titres réalisés par la communauté d'Amara.org") == ""


def test_mic_device_setting():
    assert _device(None) is None
    assert _device("") is None
    assert _device("3") == 3
    assert _device("SteelSeries") == "SteelSeries"


def test_push_to_talk_ignores_key_repeat(monkeypatch):
    hooks = {}
    monkeypatch.setattr(ptt.keyboard, "on_press_key", lambda k, cb: hooks.__setitem__("p", cb))
    monkeypatch.setattr(ptt.keyboard, "on_release_key", lambda k, cb: hooks.__setitem__("r", cb))
    calls = []
    ptt.PushToTalk("home", lambda: calls.append("start"), lambda: calls.append("stop"))

    for _ in range(5):  # touche maintenue : Windows envoie des répétitions
        hooks["p"](None)
    hooks["r"](None)
    hooks["r"](None)
    assert calls == ["start", "stop"]
