"""Mémoire de la journée (F5) : les échanges gardés sur le PC, le jour passé calculé par le
code, « de quoi on a parlé hier ? » reconnu sans le modèle."""

from datetime import date, datetime

from friday.app.prefetch import prefetcher
from friday.memory.day_log import DayLog, asks_day, day_name, past_day
from friday.tools.day_memory import RecallDayTool

TODAY = date(2026, 10, 10)  # un samedi


def test_the_past_day_is_computed_by_the_code():
    for said, expected in (("de quoi on a parlé hier ?", date(2026, 10, 9)),
                           ("et avant-hier ?", date(2026, 10, 8)),
                           ("qu'est-ce que je t'ai demandé lundi", date(2026, 10, 5)),
                           ("samedi", date(2026, 10, 3)),  # le samedi d'avant
                           ("il y a 3 jours", date(2026, 10, 7)),
                           ("le 4 octobre", date(2026, 10, 4)),
                           ("le 20 décembre", date(2025, 12, 20)),  # jamais dans le futur
                           ("résume notre journée", TODAY), ("", TODAY)):  # fmt: skip
        assert past_day(said, TODAY) == expected, said
    assert [day_name(date(2026, 10, d), TODAY) for d in (10, 9, 8, 6)] == [
        "aujourd'hui", "hier", "avant-hier", "mardi 6 octobre"]  # fmt: skip


def test_exchanges_are_kept_per_day_and_old_ones_removed(tmp_path):
    log = DayLog(tmp_path / "journee.db")
    log.add("Quel temps fait-il ?", "Il fait   beau.", datetime(2026, 10, 9, 9, 5))
    log.add("Lance ma musique", "C'est parti.", datetime(2026, 10, 9, 21, 40))
    log.add("  ", "rien", datetime(2026, 10, 9, 22, 0))  # rien de dit : rien gardé
    log.add("Bonjour", "Salut !", datetime(2026, 6, 1, 8, 0))
    assert [said for _, said, _ in log.day(date(2026, 10, 9))] == [
        "Quel temps fait-il ?", "Lance ma musique"]  # fmt: skip
    assert log.day(date(2026, 10, 9))[0][2] == "Il fait beau."
    log.prune(TODAY)  # plus de 90 jours : effacé
    assert log.day(date(2026, 6, 1)) == []
    log.close()


def test_recall_gives_the_exchanges_to_summarize(tmp_path):
    log = DayLog(tmp_path / "journee.db")
    log.add("Quel temps fait-il ?", "Il fait beau.", datetime(2026, 10, 9, 9, 5))
    log.add("Trie mes mails", "Je trie 200 mails.", datetime(2026, 10, 9, 14, 0))
    tool = RecallDayTool(log, today=lambda: TODAY)
    text = tool.run("hier").text
    assert text.startswith("Nos échanges (hier), de 09:05 à 14:00 :")
    assert "- 14:00 tu as dit « Trie mes mails » ; j'ai répondu « Je trie 200 mails. »" in text
    assert "« Hier, on a parlé de »" in text and "N'invente rien" in text
    assert tool.run("").text == ("Dis EXACTEMENT : « Je n'ai aucun échange gardé pour "
                                 "aujourd'hui. »")  # fmt: skip
    log.close()


def test_the_question_is_recognized_by_the_code():
    for text in ("De quoi on a parlé hier ?", "qu'est-ce qu'on s'est dit lundi",
                 "qu'est-ce que je t'ai demandé ce matin", "résume notre journée"):  # fmt: skip
        assert asks_day(text), text
    assert not asks_day("parle-moi de la météo")
    said = "de quoi on a parlé hier ?"
    assert prefetcher(None, None, None, days=True)(said) == ("recall_day", {"day": said})
    assert prefetcher(None, None, None)(said) is None  # mémoire de la journée coupée
