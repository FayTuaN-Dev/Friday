import threading

import pytest
from fakes import SETTINGS, FakeClient

from friday.app.reply import THINKING, Reply
from friday.brain.events import ThinkingStarted
from friday.brain.llm import Brain
from friday.brain.thinking import needs_thinking
from friday.voice.text import clean_for_speech, plain_math


@pytest.mark.parametrize(
    "text",
    [
        "Réfléchis bien : est-ce une bonne idée de changer de voiture ?",
        "Analyse ce que je viens de te dire",
        "Prends ton temps et explique-moi",
        "Combien de jours entre le 17 mars et le 2 juin ?",
        "Je roule à 90 km/h pendant 40 minutes puis à 120 km/h : quelle vitesse moyenne ?",
        "Un article à 80 € augmente de 25 % puis baisse de 20 %",
        "On partage 195,65 € en 4, ça fait combien chacun ?",
    ],
)
def test_thinking_when_asked_or_for_calculations(text):
    assert needs_thinking(text)


@pytest.mark.parametrize(
    "text",
    [
        "Bonjour Friday",
        "Mets le volume à 30",
        "Rappelle-moi d'appeler maman demain à 18 h",
        "Ajoute un rendez-vous jeudi à 14 h pendant 2 heures",  # deux nombres, pas un calcul
        "Combien font les pommes ?",  # un calcul ? pas de nombres
        "Affiche mes 5 derniers mails",
    ],
)
def test_no_thinking_for_everyday_requests(text):
    assert not needs_thinking(text)


def test_brain_thinks_only_when_needed():
    client = FakeClient(rounds=[["9 sur 4."], ["Bonjour."]])
    brain = Brain(SETTINGS, client=client)
    events = list(brain.reply("Combien font 3 fois 3 plus 4 ?"))
    assert isinstance(events[0], ThinkingStarted) and client.calls[-1]["think"] is True
    events = list(brain.reply("Bonjour"))
    assert not any(isinstance(e, ThinkingStarted) for e in events)
    assert client.calls[-1]["think"] is False


class Listener:
    def __init__(self):
        self.tools = []

    def on_reply_chunk(self, text): ...

    def on_tool(self, label):
        self.tools.append(label)


class Speaker:
    def __init__(self):
        self.said = []

    def say(self, sentence):
        self.said.append(sentence)

    def wait(self): ...


def test_reply_announces_the_thinking():
    listener, speaker = Listener(), Speaker()
    Reply(listener, speaker, threading.Event()).run(iter([ThinkingStarted(), "Le total est 12."]))
    assert speaker.said[0] in THINKING and speaker.said[-1] == "Le total est 12."
    assert listener.tools == ["🧠 Réflexion approfondie"]


def test_formulas_are_spoken_with_words():
    assert plain_math(r"$ \frac{210}{2} \approx 105 $") == " 210 sur 2  environ  105 "
    spoken = clean_for_speech(r"$ I = 12000 \times 0,04 $, soit 25 \% de plus")
    assert spoken == "I = 12000 fois 0,04 , soit 25 pour cent de plus"
    assert clean_for_speech("Rien à changer : 3 pommes.") == "Rien à changer : 3 pommes."


def test_only_the_users_own_words_count():
    from friday.briefing.briefing import REQUEST

    briefing = REQUEST.format(facts="## Météo\n17 °C, pluie 38 %, vent 12 km/h, total 3 mm")
    assert not needs_thinking(briefing)  # le briefing automatique n'est pas un calcul
    pasted = "[Texte copié par l'utilisateur :\nFacture 1 : 120 €, total 340 €\n]\nTraduis-le"
    assert not needs_thinking(pasted)
    attached = "[Fichier joint : C:/comptes_2026.xlsx]\nCombien font 12 fois 15 ?"
    assert needs_thinking(attached)  # sa propre question, elle, est un calcul


def test_generation_is_bounded_and_loops_are_reported_honestly():
    import ollama
    import pytest

    from friday.brain.llm import MAX_TOKENS, MAX_TOKENS_THINKING, BrainError

    client = FakeClient(rounds=[["ok"], ["ok"]])
    brain = Brain(SETTINGS, client=client)
    list(brain.reply("Bonjour"))
    options = client.calls[-1]["options"]
    assert options["num_predict"] == MAX_TOKENS
    list(brain.reply("Combien font 12 fois 15 plus 3 ?"))
    assert client.calls[-1]["options"]["num_predict"] == MAX_TOKENS_THINKING

    error = ollama.ResponseError("prediction aborted, token repeat limit reached", 500)
    looping = Brain(SETTINGS, client=FakeClient(error=error))
    with pytest.raises(BrainError) as caught:
        list(looping.reply("Approfondis le point 3"))
    assert caught.value.looped
    assert not BrainError("connection refused").looped
