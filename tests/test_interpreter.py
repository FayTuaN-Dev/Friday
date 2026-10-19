"""Interprète (D2) : sans vrai son du PC, ni Whisper, ni qwen (tout est simulé)."""

import threading
import time
from types import SimpleNamespace

import numpy as np

from friday.app.interpreter import Interpreter, Translator, command
from friday.app.interpreter_mode import STARTED, STOPPED, InterpreterMode
from friday.voice.loopback import pick_speaker
from friday.voice.stt import clean_transcript


def test_spoken_commands():
    for on in ("Friday, traduis la vidéo", "traduis-moi ce que j'entends",
               "mets les sous-titres sur le film", "mode interprète",
               "traduis le son du PC"):  # fmt: skip
        assert command(on) == "on", on
    for off in ("arrête de traduire", "stop la traduction", "coupe les sous-titres",
                "fin du mode interprète"):  # fmt: skip
        assert command(off) == "off", off
    for other in ("traduis son mail en anglais", "traduis bonjour en espagnol",
                  "regarde mon écran", "quelle heure est-il ?"):  # fmt: skip
        assert command(other) is None, other


def test_translator_keeps_the_model_settings_and_the_previous_line():
    calls = []

    def chat(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content="« Bonjour à tous. »"))

    translate = Translator(SimpleNamespace(chat=chat), "qwen3:8b", 16384)
    assert translate("Hello everyone.") == "Bonjour à tous."
    translate("Welcome back.")
    first, second = calls
    assert first["think"] is False and first["options"]["num_ctx"] == 16384  # pas de rechargement
    assert "Phrase précédente" not in first["messages"][1]["content"]
    assert "Phrase précédente : Hello everyone." in second["messages"][1]["content"]


class Capture:
    def __init__(self, feed):
        self.feed, self.running = feed, False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def wait(condition):
    deadline = time.monotonic() + 2
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def test_phrases_are_heard_translated_and_shown():
    heard = {1: ("Hello there.", "en"), 2: ("Salut à tous.", "fr"), 3: ("", "en")}
    shown, captures = [], []
    interpreter = Interpreter(
        lambda segment: heard[int(segment[0])],
        lambda text: f"FR({text})",
        lambda french, text: shown.append((french, text)),
        lambda feed: captures.append(Capture(feed)) or captures[-1],
        lambda on_segment: SimpleNamespace(feed=lambda audio: on_segment(audio)),
    )
    interpreter.start()
    interpreter.start()  # déjà lancé : rien de plus
    assert len(captures) == 1 and captures[0].running
    for n in (1, 2, 3):
        captures[0].feed(np.full(10, n, dtype=np.float32))
    assert wait(lambda: len(shown) == 2)
    assert shown == [("FR(Hello there.)", "Hello there."), ("Salut à tous.", "Salut à tous.")]
    interpreter.stop()
    assert not captures[0].running and not interpreter.on


def test_late_phrases_are_skipped_to_stay_live():
    gate, seen = threading.Event(), []

    def transcribe(segment):
        gate.wait(2)
        seen.append(int(segment[0]))
        return "x", "en"

    interpreter = Interpreter(transcribe, str, lambda *a: None, Capture,
                              lambda put: SimpleNamespace(feed=put))  # fmt: skip
    interpreter.start()
    phrases = interpreter._phrases
    for n in range(1, 8):
        phrases.put(np.full(4, n, dtype=np.float32))
    gate.set()
    assert wait(lambda: seen and seen[-1] == 7)
    assert len(seen) < 7  # des phrases en retard ont été sautées
    interpreter.stop()


def test_friday_starts_and_stops_on_command():
    displays, said = [], []
    listener = SimpleNamespace(on_display=displays.append, on_reply_start=lambda: None,
                               on_reply_chunk=said.append, on_reply_end=lambda i: None)  # fmt: skip
    a = SimpleNamespace(listener=listener, voice_on=False,
                        components=SimpleNamespace(stt=object(), speaker=None))  # fmt: skip
    fake = SimpleNamespace(on=False)
    fake.start = lambda: setattr(fake, "on", True)
    fake.stop = lambda: setattr(fake, "on", False)
    mode = InterpreterMode(a, make=lambda assistant: fake)
    assert not mode.command("arrête de traduire")  # pas lancé : pas une commande
    assert mode.command("Friday, traduis la vidéo") and mode.on and said == [STARTED]
    assert mode.command("arrête de traduire") and not mode.on and said[-1] == STOPPED
    assert displays[-1].kind == "subtitle" and displays[-1].data == {"off": True}
    assert not mode.command("quelle heure est-il ?")


def test_speaker_choice_and_music_noise():
    speakers = [
        SimpleNamespace(name="Speakers (GameDAC Game)"),
        SimpleNamespace(name="SteelSeries Sonar - Media (SteelSeries Sonar Virtual Audio)"),
    ]
    default = SimpleNamespace(name="défaut")
    assert pick_speaker(speakers, "SteelSeries Sonar - Media (Ste", default) is speakers[1]
    assert pick_speaker(speakers, "", default) is default
    assert pick_speaker(speakers, "absente", default) is default
    assert clean_transcript("♪ ♪") == "" and clean_transcript("Thanks for watching!") == ""
    assert clean_transcript(" Hello. ") == "Hello."


def test_subtitle_bar_shows_and_hides():
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.widgets.subtitles import SubtitleBar

    QApplication.instance() or QApplication([])
    bar = SubtitleBar()
    bar.show_text("Bonjour à tous.", "Hello everyone.")
    assert bar.isVisible() and bar.french.text() == "Bonjour à tous."
    assert not bar.heard.isHidden()
    bar.show_text("Salut.", "Salut.")  # déjà en français : pas de deuxième ligne
    assert bar.heard.isHidden()
    bar.hide()
