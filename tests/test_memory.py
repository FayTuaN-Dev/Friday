import json
import re
import zlib
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest
from fakes import SETTINGS, FakeClient

from friday.app.memory_keeper import MemoryKeeper
from friday.brain.llm import Brain
from friday.memory import service as service_module
from friday.memory.extractor import Fact, FactExtractor, date_relative_terms
from friday.memory.service import MemoryService, format_memories
from friday.memory.store import Memory, MemoryStore
from friday.tools.memory import ForgetTool, ListMemoriesTool, RememberTool


class FakeEmbedder:
    """Sac de mots : deux phrases qui partagent leurs mots ont des vecteurs proches."""

    def _vector(self, text):
        v = np.zeros(256, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            v[zlib.crc32(word.encode()) % 256] += 1
        return v / (np.linalg.norm(v) or 1)

    def documents(self, texts):
        return np.stack([self._vector(t) for t in texts])

    def query(self, text):
        return self._vector(text)


@pytest.fixture
def memory(tmp_path):
    return MemoryService(MemoryStore(tmp_path / "memory.db"), FakeEmbedder())


# --- Stockage et service ---


def test_remember_persists_across_restarts(tmp_path):
    first = MemoryService(MemoryStore(tmp_path / "m.db"), FakeEmbedder())
    first.remember("L'utilisateur s'appelle Val.", "explicit")
    again = MemoryService(MemoryStore(tmp_path / "m.db"), FakeEmbedder())
    assert [m.text for m in again.all()] == ["L'utilisateur s'appelle Val."]


def test_duplicate_is_reworded_not_added(memory):
    memory.remember("L'utilisateur adore le café.", "auto")
    memory.remember("L'utilisateur adore le café !", "auto")
    assert len(memory.all()) == 1


def test_replaces_updates_the_old_memory(memory):
    old = memory.remember("L'utilisateur habite à Lyon.", "auto")
    memory.remember("L'utilisateur a déménagé à Bordeaux.", "auto", replaces=old.id)
    assert [m.text for m in memory.all()] == ["L'utilisateur a déménagé à Bordeaux."]


def test_forget(memory):
    m = memory.remember("L'utilisateur joue de la guitare.", "explicit")
    assert memory.forget(m.id).text == m.text
    assert memory.forget(m.id) is None
    assert memory.all() == []


def test_relevant_gives_everything_when_few_then_searches(memory, monkeypatch):
    for fact in ["L'utilisateur a un chat.", "L'utilisateur boit du café.", "Pixel est le chat."]:
        memory.remember(fact, "auto")
    assert len(memory.relevant("n'importe quoi")) == 3

    monkeypatch.setattr(service_module, "ALL_IF_AT_MOST", 1)
    monkeypatch.setattr(service_module, "TOP_K", 2)
    found = [m.text for m in memory.relevant("cadeau pour mon chat")]
    assert len(found) == 2 and all("chat" in t for t in found)


def test_format_memories():
    assert format_memories([Memory(3, "L'utilisateur a un chat.", "auto", "")]) == (
        "[3] L'utilisateur a un chat."
    )


# --- Extraction automatique ---


def chat_answering(payload):
    client = SimpleNamespace(calls=[])

    def chat(**kwargs):
        client.calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=payload))

    client.chat = chat
    return client


def test_extractor_parses_facts_and_checks_replaces():
    payload = json.dumps(
        {
            "facts": [
                {"text": "L'utilisateur a déménagé à Bordeaux.", "replaces": 1},
                {"text": "L'utilisateur est développeur.", "replaces": 99},  # numéro inconnu
                {"text": "  ", "replaces": None},
            ]
        }
    )
    client = chat_answering(payload)
    known = [Memory(1, "L'utilisateur habite à Lyon.", "auto", "")]
    facts = FactExtractor(client, "qwen3:8b", 8192).extract("J'ai déménagé à Bordeaux.", known)

    assert facts == [
        Fact("L'utilisateur a déménagé à Bordeaux.", 1),
        Fact("L'utilisateur est développeur.", None),
    ]
    assert "[1] L'utilisateur habite à Lyon." in client.calls[0]["messages"][0]["content"]
    assert client.calls[0]["format"]["type"] == "object"


def test_extractor_skips_short_messages_and_bad_json():
    client = chat_answering("pas du json")
    extractor = FactExtractor(client, "qwen3:8b", 8192)
    assert extractor.extract("Merci", []) == []
    assert client.calls == []  # même pas d'appel au modèle
    assert extractor.extract("Je suis développeur Python depuis dix ans.", []) == []


def test_relative_dates_are_stamped():
    today = datetime(2026, 10, 4)
    assert date_relative_terms("Clara fête ses 30 ans samedi.", today) == (
        "Clara fête ses 30 ans samedi (noté le dimanche 4 octobre 2026)."
    )
    assert date_relative_terms("L'utilisateur s'appelle Val.", today) == (
        "L'utilisateur s'appelle Val."
    )


def test_keeper_saves_in_background(memory):
    class Extractor:
        def extract(self, text, known):
            return [Fact("L'utilisateur prépare un marathon.")]

    saved = []
    keeper = MemoryKeeper(memory, Extractor(), saved.append)
    keeper.observe("Je prépare un marathon pour avril.")
    keeper.wait_idle()
    assert saved == ["L'utilisateur prépare un marathon."]
    assert len(memory.all()) == 1


# --- Outils et prompt ---


def test_memory_tools(memory):
    result = RememberTool(memory).run("L'utilisateur est allergique aux arachides.")
    assert "mémorisé" in result.text
    lyon = RememberTool(memory).run("L'utilisateur habite à Lyon.")
    RememberTool(memory).run("L'utilisateur habite à Bordeaux.", replaces=2)
    assert "Lyon" in lyon.text and [m.text for m in memory.all()][-1].endswith("Bordeaux.")
    assert len(memory.all()) == 2
    ForgetTool(memory).run(2)
    listing = ListMemoriesTool(memory).run()
    assert listing.display.kind == "memories"
    assert listing.display.data["memories"][0]["source"] == "explicit"
    assert "oublié" in ForgetTool(memory).run(1).text
    assert "pas de souvenir" in ForgetTool(memory).run(1).text
    assert "vide" in ListMemoriesTool(memory).run().text


def test_memories_are_in_the_system_prompt():
    client = FakeClient(chunks=["ok"])
    brain = Brain(SETTINGS, client=client, recall=lambda q: "[1] L'utilisateur s'appelle Val.")
    list(brain.reply("Comment je m'appelle ?"))
    system = client.calls[0]["messages"][0]["content"]
    assert "[1] L'utilisateur s'appelle Val." in system and "forget_memory" in system

    empty = Brain(SETTINGS, client=FakeClient(chunks=["ok"]), recall=lambda q: "")
    list(empty.reply("?"))
    assert "vide pour l'instant" in empty.client.calls[0]["messages"][0]["content"]

    without = Brain(SETTINGS, client=FakeClient(chunks=["ok"]))
    list(without.reply("?"))
    assert "Ta mémoire" not in without.client.calls[0]["messages"][0]["content"]
