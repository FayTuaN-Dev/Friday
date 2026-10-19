"""Dictée partout : sans vrai micro ni vrai clavier (enregistreur, Whisper et frappe simulés)."""

import threading
from types import SimpleNamespace

import numpy as np

from friday.app.dictation import Dictation, dictated


def test_spoken_line_breaks_and_spacing():
    assert dictated(" Salut, ça va ? ") == "Salut, ça va ? "
    assert dictated("Bonjour, à la ligne, merci pour hier.") == "Bonjour\nMerci pour hier. "
    assert dictated("Fin du message point à la ligne la suite") == "Fin du message.\nLa suite "
    assert dictated("Titre. Nouveau paragraphe. Texte") == "Titre\n\nTexte "
    assert dictated("Merci à la ligne") == "Merci\n"
    assert dictated("") == "" and dictated("   ") == ""


class Recorder:
    def __init__(self):
        self.started = 0

    def start(self):
        self.started += 1

    def stop(self):
        return np.ones(16000, dtype=np.float32)


def assistant(text="Salut à tous", paused=False):
    inputs = SimpleNamespace(listening=False, calls=[])
    inputs.pause = lambda: inputs.calls.append("pause")
    inputs.resume = lambda: inputs.calls.append("resume")
    stt = SimpleNamespace(transcribe=lambda audio: text)
    return SimpleNamespace(inputs=inputs, game=SimpleNamespace(paused=paused), can_listen=True,
                           components=SimpleNamespace(recorder=Recorder(), stt=stt))  # fmt: skip


def finish():
    for thread in threading.enumerate():
        if thread.name == "dictee":
            thread.join(5)


def test_hold_speak_release_types_the_text():
    a, typed = assistant(), []
    dictation = Dictation(a, typed.append)
    dictation.press()
    dictation.press()  # répétition de la touche maintenue : un seul enregistrement
    assert dictation.recording and a.components.recorder.started == 1
    dictation.release()
    finish()
    assert typed == ["Salut à tous "] and a.inputs.calls == ["pause", "resume"]
    assert not dictation.recording


def test_no_dictation_while_talking_to_friday_in_game_mode_or_on_silence():
    a, typed = assistant(), []
    a.inputs.listening = True  # push-to-talk en cours
    Dictation(a, typed.append).press()
    assert a.components.recorder.started == 0
    paused = assistant(paused=True)  # mode jeu : Whisper est déchargé
    Dictation(paused, typed.append).press()
    assert paused.components.recorder.started == 0
    silent = Dictation(assistant(text=""), typed.append)
    silent.press()
    silent.release()
    finish()
    assert typed == []


def test_push_to_talk_waits_for_the_dictation(monkeypatch):
    from fakes import settings

    from friday.app.voice_inputs import VoiceInputs

    a = assistant()
    a.confirm = SimpleNamespace(waiting=False)
    inputs = VoiceInputs(settings(), a)
    inputs.dictation = SimpleNamespace(recording=True)
    inputs.press()
    assert not inputs.listening and a.components.recorder.started == 0
