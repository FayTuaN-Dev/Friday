import threading

from fakes import FakeTTS

from friday.voice.speaker import Speaker
from friday.voice.text import SentenceSplitter, clean_for_speech


def feed_all(splitter, chunks):
    out = []
    for c in chunks:
        out += splitter.feed(c)
    return out + splitter.flush()


def test_splitter_streams_sentences():
    s = SentenceSplitter()
    assert s.feed("Bonjour Mon") == []
    assert s.feed("sieur. Il fait") == ["Bonjour Monsieur."]
    assert s.feed(" beau ! Vraiment") == ["Il fait beau !"]
    assert s.flush() == ["Vraiment"]


def test_splitter_keeps_decimals_and_splits_long_text():
    assert feed_all(SentenceSplitter(), ["Il vaut 3.5 euros. Fin"]) == [
        "Il vaut 3.5 euros.",
        "Fin",
    ]
    long = "un mot, " * 40
    parts = feed_all(SentenceSplitter(max_chars=50), [long])
    assert len(parts) > 1
    assert all(len(p) < 120 for p in parts[:-1])


def test_clean_for_speech():
    assert clean_for_speech("**Bonjour** 😀 voir https://x.fr  !") == "Bonjour voir ce lien !"


def test_speaker_plays_in_order():
    played = []
    speaker = Speaker(
        FakeTTS(), play=lambda a, sr: played.append(a.size), stop_playback=lambda: None
    )
    for t in ["Un.", "Deux deux.", "Trois trois trois."]:
        speaker.say(t)
    speaker.wait()
    assert played == [3, 10, 18]


def test_speaker_stop_drops_pending():
    started, release, played = threading.Event(), threading.Event(), []

    def slow_play(audio, sr):
        started.set()
        release.wait(2)
        played.append(audio.size)

    speaker = Speaker(FakeTTS(), play=slow_play, stop_playback=release.set)
    for t in ["Un.", "Deux.", "Trois."]:
        speaker.say(t)
    started.wait(2)
    speaker.stop()
    speaker.wait()
    assert played == [3]  # seule la phrase déjà en cours a été jouée
