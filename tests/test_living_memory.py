"""Mémoire vivante (J1) : un fait redit est renforcé, un fait corrigé est remplacé mais gardé
dans l'historique, chaque fait a un thème et sa source ; la fiche data/memoire.md se lit ;
« d'où tu sais que… » est répondu par le code ; les anciennes bases sont migrées."""

import json
import sqlite3
from types import SimpleNamespace

import numpy as np
from test_memory import FakeEmbedder

from friday.app.prefetch import prefetcher
from friday.memory.extractor import categorize
from friday.memory.service import MemoryService
from friday.memory.store import MemoryStore
from friday.tools.memory_origin import MemoryOriginTool, asked_origin


def service(tmp_path, mirror=True):
    return MemoryService(MemoryStore(tmp_path / "memory.db"), FakeEmbedder(),
                         mirror=tmp_path / "memoire.md" if mirror else None)  # fmt: skip


def test_a_repeated_fact_is_reinforced_not_copied(tmp_path):
    memory = service(tmp_path)
    first = memory.remember("L'utilisateur adore le café.", "auto", category="goûts et loisirs")
    again = memory.remember("L'utilisateur adore le café !", "auto")
    assert again.id == first.id and again.confirmations == 2
    assert again.confidence > first.confidence
    assert len(memory.all()) == 1


def test_a_corrected_fact_is_replaced_and_kept_in_history(tmp_path):
    memory = service(tmp_path)
    old = memory.remember("L'utilisateur habite à Lyon.", "auto", category="lieu de vie",
                          said="J'habite à Lyon")  # fmt: skip
    new = memory.remember("L'utilisateur a déménagé à Bordeaux.", "auto", replaces=old.id,
                          said="J'ai déménagé à Bordeaux")  # fmt: skip
    assert [m.text for m in memory.all()] == ["L'utilisateur a déménagé à Bordeaux."]
    assert new.category == "lieu de vie"  # le thème suit
    assert [m.text for m in memory.history(new.id)] == ["L'utilisateur habite à Lyon."]
    assert memory.store.get(old.id).status == "replaced"
    memory.forget(new.id)  # « oublie » efface aussi les anciennes versions
    assert memory.store.get(old.id) is None and memory.all() == []


def test_unknown_themes_become_other(tmp_path):
    memory = service(tmp_path, mirror=False)
    assert memory.remember("L'utilisateur a un chat.", "auto", category="animaux").category == (
        "autre")  # fmt: skip


def test_the_readable_sheet_follows_the_memory(tmp_path):
    memory = service(tmp_path)
    old = memory.remember("L'utilisateur habite à Lyon.", "auto", category="lieu de vie")
    memory.remember("L'utilisateur a déménagé à Bordeaux.", "auto", replaces=old.id,
                    said="J'ai déménagé à Bordeaux")  # fmt: skip
    memory.remember("L'utilisateur trade l'or.", "explicit", category="argent et trading")
    sheet = (tmp_path / "memoire.md").read_text("utf-8")
    assert "## Lieu de vie" in sheet and "## Argent et trading" in sheet
    assert "- L'utilisateur a déménagé à Bordeaux. _(déduit, le " in sheet
    assert "  - tu as dit : « J'ai déménagé à Bordeaux »" in sheet
    assert "  - avant (jusqu'au " in sheet and ") : L'utilisateur habite à Lyon." in sheet
    assert sheet.index("Lieu de vie") < sheet.index("Argent et trading")  # ordre des thèmes


def test_where_does_a_memory_come_from(tmp_path):
    memory = service(tmp_path, mirror=False)
    old = memory.remember("L'utilisateur habite à Lyon.", "auto")
    memory.remember("L'utilisateur habite à Bordeaux.", "auto", replaces=old.id,
                    said="j'ai déménagé à Bordeaux")  # fmt: skip
    memory.remember("L'utilisateur habite à Bordeaux !", "auto")
    tool = MemoryOriginTool(memory)
    text = tool.run(asked_origin("D'où tu sais que j'habite à Bordeaux ?"))
    assert "« Tu me l'as dit le " in text.text and ": « j'ai déménagé à Bordeaux »." in text.text
    assert "Tu me l'as redit 1 fois depuis." in text.text
    assert "Avant, je savais : L'utilisateur habite à Lyon (jusqu'au " in text.text
    assert tool.run("je joue au tennis").text == (
        "Dis EXACTEMENT : « Je n'ai aucun souvenir là-dessus. »")  # fmt: skip


def test_the_origin_question_is_recognized_by_the_code():
    assert asked_origin("D'où tu sais que j'habite à Bordeaux ?") == "que j habite a bordeaux"
    assert asked_origin("qui t'a dit que j'aimais le café") == "que j aimais le cafe"
    assert asked_origin("où se trouve Bordeaux ?") is None
    said = "comment tu sais que j'ai un chat ?"
    assert prefetcher(None, None, None, memory=True)(said) == (
        "memory_origin", {"about": "que j ai un chat"})  # fmt: skip
    assert prefetcher(None, None, None)(said) is None


def test_old_databases_are_migrated(tmp_path):
    path = tmp_path / "memory.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT "
               "NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, embedding BLOB "
               "NOT NULL)")  # fmt: skip
    blob = np.zeros(256, dtype=np.float32).tobytes()
    db.execute("INSERT INTO memories VALUES (1, 'L''utilisateur a un chien.', 'auto', "
               "'2026-09-01T10:00:00', '2026-09-01T10:00:00', ?)", (blob,))  # fmt: skip
    db.commit()
    db.close()
    store = MemoryStore(path)
    (memory,) = store.all()
    assert (memory.text, memory.category, memory.confirmations, memory.status) == (
        "L'utilisateur a un chien.", "", 1, "active")  # fmt: skip
    store.close()


def test_old_memories_get_a_theme():
    payload = json.dumps({"themes": [{"id": 1, "category": "famille et proches"},
                                     {"id": 7, "category": "santé"},  # inconnu : ignoré
                                     {"id": 2, "category": "n'importe quoi"}]})  # fmt: skip

    class Client:
        def chat(self, **kwargs):
            return SimpleNamespace(message=SimpleNamespace(content=payload))

    known = [SimpleNamespace(id=1, text="La sœur de l'utilisateur s'appelle Clara."),
             SimpleNamespace(id=2, text="L'utilisateur aime le jazz.")]  # fmt: skip
    assert categorize(Client(), "qwen3:8b", known) == {1: "famille et proches", 2: "autre"}
    assert categorize(Client(), "qwen3:8b", []) == {}


def test_the_memory_sheet_opens_on_request(tmp_path):
    """Constaté : « ouvre data/memoire.md » → le Bloc-notes vide et « je n'ai pas accès »."""
    from friday.tools.memory_sheet import OpenMemorySheetTool, asks_sheet

    for said in ("Ouvre data/memoire.md", "ouvre ta fiche mémoire", "montre-moi ta fiche mémoire",
                 "affiche le fichier de ta mémoire"):  # fmt: skip
        assert asks_sheet(said), said
        assert prefetcher(None, None, None, memory=True)(said) == ("open_memory_sheet", {})
    assert not asks_sheet("qu'est-ce que tu sais sur moi ?")
    assert not asks_sheet("ouvre le Bloc-notes")
    memory, opened = service(tmp_path), []
    memory.remember("L'utilisateur s'appelle Valentin", "demande")
    said = OpenMemorySheetTool(memory, open_file=opened.append).run().text
    assert (
        opened == [str(memory.mirror)]
        and "J'ouvre ma fiche mémoire : 1 souvenir, classé par" in said
    )
    (tmp_path / "x").mkdir()
    empty = OpenMemorySheetTool(service(tmp_path / "x", mirror=False), open_file=opened.append)
    assert "n'existe pas encore" in empty.run().text and len(opened) == 1
