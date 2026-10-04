from types import SimpleNamespace

import numpy as np
import pytest

from friday.app.wake_control import WakeControl
from friday.voice.vad import FRAME, SpeechSegmenter
from friday.voice.wake import is_stop, normalize, similarity, split_wake_word, wake_pattern

WAKE = wake_pattern(["friday", "fryday", "fraidé"])


# --- Repérage du nom ---


@pytest.mark.parametrize(
    ("heard", "command"),
    [
        ("Friday, quelle heure est-il ?", "Quelle heure est-il ?"),
        ("friday quelle heure est-il", "Quelle heure est-il"),
        ("Hé Friday, quoi de neuf ?", "Quoi de neuf ?"),
        ("Et Fryday, mets de la musique.", "Mets de la musique."),  # variante de Whisper
        ("OK Fraidé… la météo ?", "La météo ?"),
        ("Hey Friday, quoi de neuf ?", "Quoi de neuf ?"),
        ("Friday.", ""),
        ("Friday ?", ""),
        ("Quelle heure est-il ?", None),
        ("J'ai parlé à Friday hier.", None),  # le nom doit être au début
        ("Fridayse est un mot inventé", None),
    ],
)
def test_split_wake_word(heard, command):
    assert split_wake_word(heard, WAKE) == command


def test_stop_commands_and_normalize():
    assert normalize("Arrête-toi !") == "arrete toi"
    assert is_stop("Stop.") and is_stop("Tais-toi !") and is_stop("C'est bon")
    assert not is_stop("Stoppe la musique et mets du jazz")


def test_similarity_detects_echo():
    said = "Il fait dix-huit degrés à Lyon, Monsieur."
    assert similarity("il fait 18 degrés à Lyon monsieur", said) > 0.6
    assert similarity("Friday, et à Paris ?", said) < 0.6


# --- Règles de réveil ---


class FakeTarget:
    def __init__(self):
        self.calls = []
        self.last_reply_text = ""
        self.busy = False
        self.awaiting_confirmation = False

    def interrupt(self):
        self.calls.append("interrupt")

    def acknowledge(self):
        self.calls.append("ack")

    def submit_heard(self, text):
        self.calls.append(("submit", text))

    def on_ignored(self, text):
        self.calls.append(("ignored", text))


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_control():
    target, clock = FakeTarget(), Clock()
    return WakeControl(target, ["friday"], follow_up_seconds=8, clock=clock), target, clock


def test_wake_word_with_request_interrupts_then_submits():
    control, target, _ = make_control()
    control.on_heard("Friday, quelle heure est-il ?")
    assert target.calls == ["interrupt", ("submit", "Quelle heure est-il ?")]


def test_without_wake_word_is_ignored():
    control, target, _ = make_control()
    control.on_heard("Tu viens manger ?")
    assert target.calls == []


def test_name_alone_acknowledges_then_accepts_next_sentence():
    control, target, clock = make_control()
    control.on_heard("Friday ?")
    assert target.calls == ["interrupt", "ack"]
    control.open_follow_up()  # (fait par l'assistant dans acknowledge)
    clock.now += 3
    control.on_heard("Quel temps fait-il ?")
    assert target.calls[-1] == ("submit", "Quel temps fait-il ?")
    control.on_heard("Et demain ?")  # la fenêtre ne sert qu'une fois
    assert target.calls[-1] == ("submit", "Quel temps fait-il ?")


def test_follow_up_window_expires():
    control, target, clock = make_control()
    control.open_follow_up()
    clock.now += 9
    control.on_heard("Et demain ?")
    assert target.calls == [("ignored", "Et demain ?")]  # pas traité, mais signalé


def test_stop_only_interrupts():
    control, target, _ = make_control()
    control.on_heard("Friday, stop !")
    assert target.calls == ["interrupt"]


def test_short_stop_works_without_name_while_speaking():
    control, target, _ = make_control()
    control.on_heard("Ravi, stop.")  # au repos : ignoré
    assert target.calls == []
    target.busy = True
    control.on_heard("Ravi, stop.")  # « Friday, stop » mal transcrit
    control.on_heard("Tais-toi !")
    control.on_heard("Il faut que tu arrêtes de fumer, stop")  # trop long : pas un ordre
    assert target.calls == ["interrupt", "interrupt"]


def test_own_echo_is_ignored_even_with_name():
    control, target, _ = make_control()
    target.last_reply_text = "Friday, à votre service. Il fait beau aujourd'hui."
    control.open_follow_up()
    control.on_heard("Friday à votre service, il fait beau aujourd'hui.")
    control.on_heard("Il fait beau aujourd'hui")
    assert target.calls == []


# --- Découpage en phrases (VAD) ---


def energy_vad(frame):
    """Faux VAD : de la « parole » dès que le signal est fort."""
    return 1.0 if np.abs(frame).mean() > 0.1 else 0.0


def frames(seconds, loud):
    n = int(seconds * 16000) // FRAME * FRAME
    return np.full(n, 0.5 if loud else 0.0, dtype=np.float32)


def test_segmenter_cuts_sentences_on_silence():
    segments = []
    seg = SpeechSegmenter(energy_vad, segments.append, silence_ms=500, preroll_ms=200)
    audio = np.concatenate(
        [frames(1, False), frames(1.5, True), frames(1, False), frames(0.8, True), frames(1, False)]
    )
    for i in range(0, audio.size, 320):  # blocs de 20 ms comme le micro
        seg.feed(audio[i : i + 320])

    assert len(segments) == 2
    # parole + un peu d'avant (pré-enregistrement) + le silence de fin
    assert 1.5 < segments[0].size / 16000 < 2.4
    assert not seg.in_speech


def test_segmenter_ignores_short_noises_and_caps_length():
    segments = []
    seg = SpeechSegmenter(energy_vad, segments.append, silence_ms=300, max_ms=2000)
    seg.feed(np.concatenate([frames(0.1, True), frames(1, False)]))  # un claquement
    assert segments == []
    seg.feed(frames(5, True))  # quelqu'un qui parle sans s'arrêter
    assert len(segments) == 2 and all(s.size / 16000 <= 2.1 for s in segments)


def test_long_sentence_started_in_window_counts():
    """Le bug du test réel : « Friday. » → « Oui ? » → longue phrase commencée dans la
    fenêtre, mais transcrite après sa fin."""
    control, target, clock = make_control()
    control.open_follow_up()  # fenêtre jusqu'à 108
    started = clock.now + 6
    clock.now += 11  # transcription terminée après la fin de la fenêtre
    control.on_heard("J'ai fait des recherches sur le pétrole.", spoken_at=started)
    assert target.calls[-1] == ("submit", "J'ai fait des recherches sur le pétrole.")


def test_phrase_just_after_window_is_reported_not_silently_dropped():
    control, target, clock = make_control()
    control.on_heard("Tu fais quoi ?")  # au démarrage : rien de récent, rien signalé
    assert target.calls == []
    control.open_follow_up()
    clock.now += 12
    control.on_heard("Tu fais pas de recherche ?")
    assert target.calls == [("ignored", "Tu fais pas de recherche ?")]
    clock.now += 60
    control.on_heard("On mange quoi ?")  # bien plus tard : conversation normale
    assert target.calls == [("ignored", "Tu fais pas de recherche ?")]


def test_segmenter_records_when_speech_started():
    segments = []
    times = iter(range(1000))
    seg = SpeechSegmenter(energy_vad, segments.append, silence_ms=300, clock=lambda: next(times))
    seg.feed(np.concatenate([frames(0.5, False), frames(1, True), frames(0.5, False)]))
    assert len(segments) == 1 and seg.started_at == 0  # 1er appel à l'horloge = début


def test_confirmation_answer_needs_no_name():
    control, target, _ = make_control()
    target.awaiting_confirmation = True
    control.on_heard("Oui, vas-y.")
    control.on_heard("Friday, non.")
    assert target.calls == [("submit", "Oui, vas-y."), ("submit", "Non.")]


def test_request_started_while_friday_says_yes_is_accepted():
    """Le bug du test réel : « Friday » → il répond « Oui ? » → la demande, commencée
    pendant sa réponse, était ignorée (la fenêtre ne s'ouvrait qu'après)."""
    from friday.app.hands_free_target import HandsFreeTarget

    clock = Clock()
    said = []
    speaker = SimpleNamespace(say=said.append, wait=lambda: setattr(clock, "now", clock.now + 2))
    assistant = SimpleNamespace(
        settings=SimpleNamespace(user_name="Monsieur", wake_words=["friday"]),
        listener=SimpleNamespace(on_notice=lambda text: None),
        voice_on=True, components=SimpleNamespace(speaker=speaker), busy=False,
        reply_spoken="", confirm=SimpleNamespace(waiting=False),
        interrupt=lambda: None, submit_heard=lambda text: submitted.append(text),
    )  # fmt: skip
    submitted = []
    target = HandsFreeTarget(assistant)
    target.wake = WakeControl(target, ["friday"], follow_up_seconds=8, clock=clock)

    started = clock.now + 0.5  # on parle pendant « Oui, Monsieur ? »
    target.wake.on_heard("Friday")
    clock.now += 4
    target.wake.on_heard("Ajoute du pain à ma liste de courses", spoken_at=started)
    assert said == ["Oui, Monsieur ?"]
    assert submitted == ["Ajoute du pain à ma liste de courses"]


def test_heard_log_keeps_recent_recordings(tmp_path, monkeypatch):
    import wave

    from friday.voice import heard_log

    monkeypatch.setattr(heard_log, "KEEP", 2)
    log = heard_log.HeardLog(tmp_path)
    for text in ["Lance Spotify", "Ajoute du pain", "Friday, stop"]:
        path = log.save(np.zeros(1600, dtype=np.float32), text)
    assert len(list(tmp_path.glob("*.wav"))) == 2  # le plus ancien est effacé
    assert path.with_suffix(".txt").read_text(encoding="utf-8") == "Friday, stop"
    with wave.open(str(path)) as wav:
        assert wav.getframerate() == 16000 and wav.getnframes() == 1600


def test_english_name_is_rescued_from_the_start_of_the_sentence():
    """« Friday » (anglais) sauté par Whisper réglé en français : on retranscrit le début en
    anglais, et on remet le nom devant la phrase."""
    from friday.app.voice_inputs import VoiceInputs

    class STT:
        def transcribe(self, audio):
            return {"avec": "Ajoute du pain.", "sans": "Tu viens manger ?"}[audio]

        def transcribe_head(self, audio, language, seconds=1.3):
            assert language == "en"
            return {"avec": "Friday, add", "sans": "Do you come"}[audio]

    settings = SimpleNamespace(wake_words=["friday"], follow_up_seconds=8, wake_language="en")
    inputs = VoiceInputs(settings, SimpleNamespace())
    transcribe = inputs._with_wake_rescue(STT())
    assert transcribe("avec") == "Friday, Ajoute du pain."
    assert transcribe("sans") == "Tu viens manger ?"

    settings.wake_language = "fr"  # nom français : pas de seconde transcription
    plain = VoiceInputs(settings, SimpleNamespace())._with_wake_rescue(STT())
    assert plain("avec") == "Ajoute du pain."  # (transcribe_head n'est jamais appelé)


def test_name_pronunciation():
    from friday.voice.text import apply_pronunciations

    assert apply_pronunciations("Je suis Friday, Monsieur.", {"friday": "Fraille dé"}) == (
        "Je suis Fraille dé, Monsieur."
    )
    assert apply_pronunciations("Fridays", {"friday": "X"}) == "Fridays"  # mot entier seulement
