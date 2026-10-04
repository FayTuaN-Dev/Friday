from types import SimpleNamespace

import numpy as np

from friday.core.config import _device
from friday.voice import ptt
from friday.voice.recorder import resample
from friday.voice.stt import clean_transcript


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


def key(event_type):
    return SimpleNamespace(event_type=event_type)


def test_push_to_talk_ignores_key_repeat_and_unhooks(monkeypatch):
    hooks = {}
    monkeypatch.setattr(ptt.keyboard, "hook_key", lambda k, cb: hooks.setdefault(k, cb))
    monkeypatch.setattr(ptt.keyboard, "unhook", lambda h: hooks.clear())
    calls = []
    push = ptt.PushToTalk("home", lambda: calls.append("start"), lambda: calls.append("stop"))

    for _ in range(5):  # touche maintenue : Windows envoie des répétitions
        hooks["home"](key("down"))
    hooks["home"](key("up"))
    hooks["home"](key("up"))
    assert calls == ["start", "stop"]

    push.close()
    push.close()  # deux fois sans erreur
    assert hooks == {}
