"""Rêve nocturne (J2) : relire une journée entière pour retrouver les faits manqués, préparer
un rapport de ménage (contradictions, faits jamais redits, erreurs répétées) sans rien
appliquer, une seule fois par jour, la nuit ou quand Friday est inactive, en silence."""

import json
from datetime import date, datetime
from types import SimpleNamespace

from test_memory import FakeEmbedder

from friday.app.night_dream import TASK, NightDream
from friday.app.notification import QUIET
from friday.app.prefetch import prefetcher
from friday.memory.day_log import DayLog
from friday.memory.dream import Dreamer, repeated_errors, stale
from friday.memory.service import MemoryService
from friday.memory.store import Memory, MemoryStore
from friday.tools.dream_report import DreamReportTool, asks_dream

NOW = datetime(2026, 10, 11, 3, 15)  # la nuit


class Client:
    """Répond aux deux questions du rêve : faits manqués, puis paires à vérifier."""

    def __init__(self, facts, pairs):
        self.facts, self.pairs, self.prompts = facts, pairs, []

    def chat(self, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        self.prompts.append(prompt)
        if "Réécris chaque phrase" in prompt:  # au tutoiement
            lines = [line.split(". ", 1)[1] for line in prompt.splitlines()
                     if line[:1].isdigit()]  # fmt: skip
            you = [line.replace("L'utilisateur habite", "tu habites")
                   .replace("L'utilisateur vit", "tu vis").rstrip(".")
                   for line in lines]  # fmt: skip
            return SimpleNamespace(message=SimpleNamespace(content=json.dumps({"phrases": you})))
        key = "facts" if "Phrases de l'utilisateur" in prompt else "pairs"
        payload = {key: self.facts if key == "facts" else self.pairs(prompt)}
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))


def setup(tmp_path, facts, pairs=lambda prompt: []):
    memory = MemoryService(MemoryStore(tmp_path / "memory.db"), FakeEmbedder())
    log = DayLog(tmp_path / "journee.db")
    client = Client(facts, pairs)
    (tmp_path / "friday.log").write_text("", "utf-8")
    dream = NightDream(memory, log, Dreamer(client, "qwen3:8b", 16384), tmp_path / "reve",
                       tmp_path / "friday.log", on_done=lambda *a: calls.append(a))  # fmt: skip
    calls = []
    return memory, log, client, dream, calls


def test_a_day_is_reread_and_missed_facts_kept(tmp_path):
    memory, log, client, dream, calls = setup(tmp_path, [
        {"text": "La copine de l'utilisateur s'appelle Emma.", "line": 2, "replaces": None,
         "category": "famille et proches"},
        {"text": "Inventé", "line": 9, "replaces": None, "category": "autre"}])  # fmt: skip
    log.add("Tu connais ma copine ?", "Non, comment s'appelle-t-elle ?", datetime(2026, 10, 10, 20))
    log.add("Emma", "Enchantée !", datetime(2026, 10, 10, 20, 1))
    (report,) = dream.tick(NOW)
    assert report.day == "2026-10-10" and report.exchanges == 2
    assert report.added == ["La copine de l'utilisateur s'appelle Emma."]  # ligne 9 : ignorée
    (kept,) = memory.all()
    assert (kept.said, kept.category) == ("Emma", "famille et proches")
    assert "2. [« Non, comment s'appelle-t-elle ? »] Emma" in client.prompts[0]  # le contexte
    assert calls[0][0] == TASK and TASK in QUIET  # notification seulement, pas de voix
    assert dream.tick(NOW) == []  # une seule fois par jour
    assert "La copine" in (tmp_path / "reve" / "2026-10-10.md").read_text("utf-8")


def test_the_cleanup_is_only_proposed(tmp_path):
    def pairs(prompt):
        return [{"a": 1, "b": 2, "kind": "contradiction"}, {"a": 2, "b": 1, "kind": "doublon"},
                {"a": 1, "b": 99, "kind": "doublon"}]  # fmt: skip

    memory, log, _, dream, _ = setup(tmp_path, [], pairs)
    memory.remember("L'utilisateur habite à Lyon.", "auto")
    memory.remember("L'utilisateur vit aux Herbiers.", "auto")
    log.add("Salut", "Bonjour !", datetime(2026, 10, 10, 9))
    (report,) = dream.tick(NOW)
    assert [(p.first.id, p.second.id, p.kind) for p in report.pairs] == [(1, 2, "contradiction")]
    assert len(memory.all()) == 2  # rien n'a été changé
    text = DreamReportTool(tmp_path / "reve", today=lambda: date(2026, 10, 11)).run().text
    assert text == ("Dis EXACTEMENT : « Cette nuit, j'ai relu notre échange d'hier : rien de "
                    "nouveau à retenir. Une contradiction : tu habites à Lyon, ou tu vis aux "
                    "Herbiers ? Lequel est juste ? »")  # fmt: skip


def test_when_to_dream(tmp_path):
    _, log, _, dream, _ = setup(tmp_path, [])
    assert dream.tick(NOW) == []  # aucune journée avec des échanges
    log.add("Salut", "Bonjour", datetime(2026, 10, 11, 14, 0))  # on parle encore aujourd'hui
    log.add("Hier soir", "Ok", datetime(2026, 10, 10, 22, 0))
    afternoon = datetime(2026, 10, 11, 14, 10)
    assert not dream.can_run(afternoon)  # Friday est utilisée : pas maintenant
    assert dream.can_run(datetime(2026, 10, 11, 14, 31))  # 30 min sans parler
    assert dream.can_run(NOW)
    assert dream.due_days(afternoon) == [date(2026, 10, 10)]  # jamais aujourd'hui


def test_stale_facts_and_repeated_errors(tmp_path):
    old = Memory(1, "L'utilisateur fait du judo.", "auto", "", created_at="2026-01-02T10:00:00")
    redit = Memory(2, "L'utilisateur aime le jazz.", "auto", "", confirmations=3,
                   created_at="2026-01-02T10:00:00")  # fmt: skip
    asked = Memory(3, "L'utilisateur s'appelle Val.", "explicit", "",
                   created_at="2026-01-02T10:00:00")  # fmt: skip
    assert stale([old, redit, asked], NOW) == [old]
    journal = tmp_path / "friday.log"
    journal.write_text("\n".join(
        ["23:16:31 [WARNING] friday.voice.player: Coupure audio pendant la lecture (1)",
         "23:17:02 [WARNING] friday.voice.player: Coupure audio pendant la lecture (2)",
         "08:00:00 [INFO] friday.app: Démarrage",
         "09:12:40 [WARNING] friday.voice.player: Coupure audio pendant la lecture (7)",
         "10:00:00 [ERROR] friday.brain.llm: Erreur Ollama"]), "utf-8")  # fmt: skip
    assert repeated_errors(journal) == [("Coupure audio pendant la lecture (#)", 3)]
    assert repeated_errors(tmp_path / "absent.log") == []


def test_the_report_question_is_recognized(tmp_path):
    for text in ("Qu'as-tu fait cette nuit ?", "tu as rêvé ?", "donne-moi le rapport de la nuit"):
        assert asks_dream(text), text
    assert not asks_dream("il a fait froid la nuit")
    assert prefetcher(None, None, None, memory=True)("qu'as-tu fait cette nuit ?") == (
        "dream_report", {})  # fmt: skip
    empty = DreamReportTool(tmp_path / "reve").run().text
    assert empty.startswith("Dis EXACTEMENT : « Je n'ai pas encore rêvé")


def test_the_report_sentence_is_built_by_the_code():
    from friday.tools.dream_report import sentence

    data = {"day": "2026-10-09", "exchanges": 5,
            "added": ["L'utilisateur pratique le judo.", "L'utilisateur a un chat, Pixel."],
            "pairs": [], "stale": [[4, "L'utilisateur aime le jazz."]],
            "errors": [["Coupure audio pendant la lecture (#)", 4]],
            "you": {"L'utilisateur pratique le judo.": "tu pratiques le judo",
                    "L'utilisateur a un chat, Pixel.": "tu as un chat, Pixel",
                    "L'utilisateur aime le jazz.": "tu aimes le jazz"}}  # fmt: skip
    assert sentence(data, date(2026, 10, 10)) == (
        "Cette nuit, j'ai relu nos 5 échanges d'hier et j'ai retenu que tu pratiques le judo et "
        "tu as un chat, Pixel. Est-ce toujours vrai que tu aimes le jazz ? Et une erreur revient "
        "souvent dans mon journal (4 fois) : Coupure audio pendant la lecture (…).")  # fmt: skip
    data.update(added=[], stale=[], errors=[])
    assert sentence(data, date(2026, 10, 10)).endswith("à retenir. Rien à vérifier.")
