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


def test_the_light_brain_reads_its_instructions_at_startup_and_stays_loaded():
    client = FakeClient(chunks=["."])
    brain = Brain(SETTINGS, client=client, light_guides="- get_weather : la météo.")
    brain.warmup()
    sent = client.calls[0]
    assert sent["keep_alive"] == -1 and sent["messages"][0]["role"] == "system"
    assert sent["options"]["num_predict"] == 1  # lire, pas écrire


class DoneClient(FakeClient):
    """Comme Ollama : le dernier morceau dit combien de jetons ont été lus et écrits."""

    def chat(self, **kwargs):
        stream = super().chat(**kwargs)
        if stream is None:
            return None
        done = SimpleNamespace(message=SimpleNamespace(content="", tool_calls=None), done=True,
                               prompt_eval_count=1900, eval_count=30)  # fmt: skip
        return [*stream, done]


def test_the_slow_pi_never_triggers_the_reload_meant_for_the_graphics_card():
    # Constaté : la sécurité du PC (lecture sous 500 jetons/s → rechargement) rechargeait le
    # modèle du Pi (22 jetons/s) presque à chaque question : 87 s de relecture
    for guides, watched in ((None, True), ("- outil.", False)):
        brain = Brain(SETTINGS, client=DoneClient(chunks=["Oui."]), light_guides=guides)
        seen = []
        brain.speed.record = seen.append
        assert "".join(brain.reply("Bonjour")) == "Oui."
        assert bool(seen) is watched


class FakeBrain:
    def __init__(self, fail=False):
        self.fail, self.resets = fail, 0

    def reply(self, text):
        if self.fail:
            raise BrainError("Ollama absent")
        yield ToolStarted("get_weather", {}, "🌤️ Météo : Lyon")
        yield "Demain, "
        yield "du soleil. 😊"

    def reset(self):
        self.resets += 1


def test_answers_are_sent_line_by_line_and_errors_said_plainly():
    assert list(lines_of(FakeBrain(), "météo ?")) == [
        {"outil": "🌤️ Météo : Lyon"}, {"texte": "Demain, "}, {"texte": "du soleil. "},
        {"fin": True}]  # fmt: skip
    assert list(lines_of(FakeBrain(fail=True), "?"))[0]["erreur"].startswith("Le modèle")


class FakeEar:
    def hear(self, data):
        return "quel temps demain" if data == b"voix" else ""


def serving(brain):
    handler = make_handler(SimpleNamespace(brain=brain), "cle-secrete", "qwen3:4b", FakeEar(),
                           "moi@exemple.fr")  # fmt: skip
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
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
        assert (
            state["pret"]
            and state["modele"] == "qwen3:4b"
            and "last_message" not in state["machine"]
        )
        lines = httpx.post(f"{url}/api/message", json={"texte": "météo ?"}, headers=good).text
        assert [json.loads(x) for x in lines.splitlines()][-1] == {"fin": True}
        machine = httpx.get(f"{url}/api/etat", headers=good).json()["machine"]
        assert machine["last_message"] > 0  # la carte « Pi » du PC : dernière question
        httpx.post(f"{url}/api/nouvelle", json={}, headers=good)
        assert brain.resets == 1
        said = []
        talk(ServerSettings(0, "cle-secrete", url), "météo ?",
             out=lambda *a, **k: said.append("".join(map(str, a))))  # fmt: skip
        assert "[🌤️ Météo : Lyon]" in "".join(said) and "du soleil." in "".join(said)
    finally:
        server.shutdown()


def test_the_phone_enters_with_its_tailscale_account_and_speaks():
    server, url = serving(FakeBrain())
    try:
        mine = {"Tailscale-User-Login": "Moi@Exemple.fr"}  # ajouté par « tailscale serve »
        other = {"Tailscale-User-Login": "quelquun@ailleurs.fr"}
        assert httpx.get(f"{url}/api/etat", headers=other).status_code == 401
        page = httpx.get(f"{url}/", headers=mine)
        assert page.status_code == 200 and "F.R.I.D.A.Y." in page.text
        assert httpx.get(f"{url}/icone-512.png", headers=mine).content[1:4] == b"PNG"
        assert httpx.get(f"{url}/../.env", headers=mine).status_code == 404
        heard = httpx.post(f"{url}/api/audio", content=b"voix", headers=mine).text.splitlines()
        assert json.loads(heard[0]) == {"vous": "quel temps demain"}
        assert json.loads(heard[-1]) == {"fin": True}
        silence = httpx.post(f"{url}/api/audio", content=b"bruit", headers=mine).text
        assert "rien entendu" in silence
    finally:
        server.shutdown()


def test_a_recording_is_decoded_to_what_whisper_expects():
    import io
    import wave

    import numpy as np

    from friday.server.ear import decode

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:  # 1 s à 48 kHz, stéréo, comme un téléphone
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(48000)
        tone = (np.sin(np.arange(48000) / 48000 * 2 * np.pi * 440) * 12000).astype(np.int16)
        w.writeframes(np.repeat(tone, 2).tobytes())
    audio = decode(buffer.getvalue())
    assert abs(len(audio) - 16000) < 400 and audio.dtype == np.float32
    assert 0.2 < np.abs(audio).max() <= 1.0
