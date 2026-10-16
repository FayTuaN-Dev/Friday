import json
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import httpx
from fakes import SETTINGS, FakeClient

from friday.brain.events import ToolStarted
from friday.brain.llm import Brain, BrainError
from friday.server.client import talk
from friday.server.http_api import lines_of, make_handler
from friday.server.settings import ServerSettings


def test_the_light_brain_keeps_its_instructions_identical_from_one_question_to_the_next():
    # Sur le Pi, Ollama ne relit pas un début de demande inchangé : consignes FIXES
    client = FakeClient(chunks=["D'accord."])
    brain = Brain(SETTINGS, client=client, recall=lambda q: f"[1] souvenir sur {q}",
                  light_guides="- get_weather : la météo.")  # fmt: skip
    list(brain.reply("Bonjour"))
    list(brain.reply("Et demain ?"))
    first, second = (call["messages"] for call in client.calls)
    assert first[0] == second[0] and "get_weather : la météo" in first[0]["content"]
    assert "souvenir sur" not in first[0]["content"]  # ce qui change va avec la question
    question = second[-1]["content"]
    assert (
        question.startswith("[Contexte : nous sommes le ") and "souvenir sur Et demain" in question
    )
    assert question.endswith("Et demain ?")
    assert brain.conversation.messages[0]["content"] == "Bonjour"  # l'historique, lui, intact


class FakeBrain:
    def __init__(self, fail=False):
        self.fail, self.resets = fail, 0

    def reply(self, text):
        if self.fail:
            raise BrainError("Ollama absent")
        yield ToolStarted("get_weather", {}, "🌤️ Météo : Lyon")
        yield "Demain, "
        yield "du soleil."

    def reset(self):
        self.resets += 1


def test_answers_are_sent_line_by_line_and_errors_said_plainly():
    assert list(lines_of(FakeBrain(), "météo ?")) == [
        {"outil": "🌤️ Météo : Lyon"}, {"texte": "Demain, "}, {"texte": "du soleil."},
        {"fin": True}]  # fmt: skip
    assert list(lines_of(FakeBrain(fail=True), "?"))[0]["erreur"].startswith("Le modèle")


def serving(brain):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
        SimpleNamespace(brain=brain), "cle-secrete", "qwen3:4b"))  # fmt: skip
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_the_server_refuses_without_the_key_and_answers_with_it():
    brain = FakeBrain()
    server, url = serving(brain)
    try:
        assert httpx.get(f"{url}/api/etat").status_code == 401
        bad = {"Authorization": "Bearer mauvaise"}
        assert httpx.post(f"{url}/api/message", json={"texte": "?"}, headers=bad).status_code == 401
        good = {"Authorization": "Bearer cle-secrete"}
        state = httpx.get(f"{url}/api/etat", headers=good).json()
        assert state == {"pret": True, "modele": "qwen3:4b"}
        lines = httpx.post(f"{url}/api/message", json={"texte": "météo ?"}, headers=good).text
        assert [json.loads(x) for x in lines.splitlines()][-1] == {"fin": True}
        httpx.post(f"{url}/api/nouvelle", json={}, headers=good)
        assert brain.resets == 1
        said = []
        talk(ServerSettings(0, "cle-secrete", url), "météo ?",
             out=lambda *a, **k: said.append("".join(map(str, a))))  # fmt: skip
        assert "[🌤️ Météo : Lyon]" in "".join(said) and "du soleil." in "".join(said)
    finally:
        server.shutdown()
