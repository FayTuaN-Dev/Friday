"""Le carnet de plans écrits : autant de stratégies écrites que voulu, chacune traduite (après
aperçu), testée, comparée, choisie ; le plan unique d'avant est repris ; le plan suivi est
celui joint aux analyses de Claude."""

import json
import time

from test_written_plan import BREAKOUT, REPLI

from friday.app.prefetch import plan_request
from friday.tools.plan_translate import TranslatePlanTool, which_plan
from friday.trading.journal import TradeJournal
from friday.trading.plan_book import PlanBook
from friday.trading.strategy_choice import DEFAULT, StrategyChoice


def book_with(tmp_path, *plans):
    book = PlanBook(tmp_path / "plans.json")
    for name, text, spec in plans:
        plan = book.add(name, text)
        if spec:
            book.save_translation(plan["id"], spec, text)
    return book


def test_the_book_keeps_named_plans(tmp_path):
    book = book_with(tmp_path, ("Cassure Londres", "Cassure 24 h.", BREAKOUT),
                     ("Repli EMA", "Repli EMA50.", None))  # fmt: skip
    first, second = book.plans()
    assert (first["id"], second["id"]) == ("p1", "p2") and second["spec"] is None
    assert book.add("Cassure Londres")["nom"] == "Cassure Londres 2"  # noms uniques
    copy = book.duplicate("p1")
    assert copy["nom"] == "Cassure Londres (copie)" and copy["spec"] is None  # à retraduire
    book.update("p2", nom="Repli strict", texte="Repli EMA50 strict.")
    assert book.get("p2")["nom"] == "Repli strict"
    assert book.find("teste le plan cassure londres sur l'or")["id"] == "p1"
    assert book.find("teste le plan Cassure Londres 2")["id"] == "p3"  # le nom le plus long
    assert book.find("que penses-tu de l'or ?") is None
    assert not book.outdated(book.get("p1"))
    book.update("p1", texte="Cassure 48 h.")
    assert book.outdated(book.get("p1"))  # modifié depuis la traduction
    assert book.delete("p2") and not book.delete("p2")
    assert [s.label for s in book.strategies()] == ["ton plan « Cassure Londres »"]


def test_the_single_plan_from_before_is_adopted(tmp_path):
    (tmp_path / "plan.txt").write_text("Repli EMA50 en tendance.", "utf-8")
    (tmp_path / "rules.json").write_text(
        json.dumps({"spec": REPLI, "empreinte": "abc", "traduit_le": "08/10/2026 à 11:55"}), "utf-8"
    )
    book = PlanBook(tmp_path / "plans.json", tmp_path / "plan.txt", tmp_path / "rules.json")
    (plan,) = book.plans()
    assert plan["nom"] == "Mon plan" and plan["texte"] == "Repli EMA50 en tendance."
    assert plan["spec"] is not None and plan["traduit_le"] == "08/10/2026 à 11:55"
    again = PlanBook(tmp_path / "plans.json", tmp_path / "plan.txt", tmp_path / "rules.json")
    assert len(again.plans()) == 1  # une seule fois
    assert PlanBook(tmp_path / "vide.json", tmp_path / "rien.txt").plans() == []


def test_every_translated_plan_is_a_strategy_to_choose(tmp_path):
    book = book_with(tmp_path, ("Cassure Londres", "Cassure 24 h.", BREAKOUT),
                     ("Repli EMA", "Repli EMA50.", REPLI), ("Brouillon", "…", None))  # fmt: skip
    choice = StrategyChoice(tmp_path / "s.json", book)
    names = [s.name for s in choice.available()]
    assert names[:3] == ["plan:p1", "plan:p2", "repli"]  # brouillon non traduit : absent
    assert choice.get("XAUUSD").name == "plan:p1"  # par défaut : le premier plan traduit
    choice.set("XAUUSD", "plan:p2")
    choice.set(DEFAULT, "cassure")
    assert choice.get("XAUUSD").label == "ton plan « Repli EMA »"
    assert choice.get("EURUSD").name == "cassure"
    assert choice.plan_text("XAUUSD") == "Plan « Repli EMA » :\nRepli EMA50."  # pour Claude
    assert choice.plan_text("EURUSD").startswith("Stratégie suivie : la cassure de range")
    book.delete("p2")
    assert choice.get("XAUUSD").name == "repli"  # plan supprimé : le modèle


def test_the_code_finds_the_named_plan_in_requests(tmp_path):
    book = book_with(tmp_path, ("Cassure Londres", "x", BREAKOUT))
    assert plan_request("teste le plan Cassure Londres sur l'or", book) == (
        "backtest_plan", {"instrument": "XAUUSD", "plan": "p1"})  # fmt: skip
    assert plan_request("traduis le plan Cassure Londres", book) == (
        "translate_plan", {"request": "traduis le plan Cassure Londres"})  # fmt: skip
    tool, args = plan_request("choisis le plan Cassure Londres pour l'or", book)
    assert tool == "choose_strategy" and args["instrument"] == "XAUUSD"
    assert plan_request("que penses-tu de l'or ?", book) is None


class Job:
    def __init__(self, answer):
        self.answer, self.task = answer, None

    @property
    def busy(self):
        return False

    def run(self, content, options=None):
        return {"ok": True, "result": self.answer}


def wait(items):
    for _ in range(100):
        if items:
            return
        time.sleep(0.02)


def test_translation_of_the_named_plan(tmp_path):
    book = book_with(tmp_path, ("Cassure Londres", "Cassure 24 h. Compte de 5 000 €.", None),
                     ("Repli EMA", "Repli EMA50.", None))  # fmt: skip
    choice, done = StrategyChoice(tmp_path / "s.json", book), []
    tool = TranslatePlanTool(choice, Job(json.dumps(BREAKOUT)), TradeJournal(tmp_path / "t.db"),
                             lambda task, result: done.append(result))  # fmt: skip
    assert tool.confirmation({}) is None and "Quel plan dois-je traduire" in tool.run().text
    asked = {"request": "traduis le plan Cassure Londres"}
    assert "J'envoie ton plan « Cassure Londres »" in tool.confirmation(asked)
    packet = tool.preview(asked)
    assert "5 000" not in packet.items[0].text  # masqué
    packet.approved = True
    launched = tool.run(**asked).text  # une phrase fixe : rien d'inventé avant la réponse
    assert launched.startswith("Dis EXACTEMENT") and "je te préviens" in launched
    wait(done)
    assert book.get("p1")["spec"] is not None and book.get("p2")["spec"] is None
    assert "Le plan « Cassure Londres » est traduit en règles" in done[0].text
    assert which_plan(choice, "p2")["nom"] == "Repli EMA"


def test_the_settings_edit_several_plans(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.trading_plan import NOT_YET, TradingPlanRow
    from friday.ui.desktop.settings.trading_strategy import StrategyRow

    QApplication.instance() or QApplication([])
    book = PlanBook(tmp_path / "plans.json")
    asked = []
    row = TradingPlanRow(book, asked.append)
    assert "Aucun plan" in row.rules.text()
    row._new()
    row.name.setText("Cassure Londres")
    row.editor.setPlainText("Cassure du plus haut de 24 h.")
    row._translate()
    assert (
        asked == ["Cassure Londres"] and book.get("p1")["texte"] == "Cassure du plus haut de 24 h."
    )
    assert row.rules.text() == NOT_YET
    book.save_translation("p1", BREAKOUT, "Cassure du plus haut de 24 h.")
    row.reload()
    assert row.picker.currentText() == "Cassure Londres ✅" and "✅ Traduit le" in row.rules.text()
    row._duplicate()
    assert row.picker.count() == 2 and row.name.text() == "Cassure Londres (copie)"
    row._delete()
    row._delete()  # deux clics
    assert [p["nom"] for p in book.plans()] == ["Cassure Londres"]
    choice = StrategyChoice(tmp_path / "s.json", book)
    strategies = StrategyRow(choice)
    assert strategies.box.itemText(0) == "Ton plan « Cassure Londres »"
    strategies.box.setCurrentIndex(strategies.box.findData("retour"))
    assert choice.get("XAUUSD").name == "retour"


def test_a_plan_too_long_is_refused_out_loud_not_cut_silently(tmp_path):
    # Constaté : Turtle Traders, coupé à 1 500 caractères avant ses entrées → « aucune
    # condition d'entrée », sans que rien ne le dise
    from PySide6.QtWidgets import QApplication

    from friday.trading.plan_book import TEXT_CHARS
    from friday.ui.desktop.settings.trading_plan import TradingPlanRow

    QApplication.instance() or QApplication([])
    book = PlanBook(tmp_path / "plans.json")
    asked = []
    row = TradingPlanRow(book, asked.append)
    row._new()
    row.name.setText("Turtle Traders")
    row.editor.setPlainText("Entrée : cassure du plus haut de 20 jours. " * 60)  # ~2 600
    assert "/ 4 000 caractères" in row.count.text() and "trop long" not in row.count.text()
    row._translate()
    assert asked == ["Turtle Traders"] and len(book.get("p1")["texte"]) > 2500  # gardé entier
    row.editor.setPlainText("x" * (TEXT_CHARS + 10))
    assert "trop long" in row.count.text()
    row._translate()
    assert asked == ["Turtle Traders"] and "10 caractères de trop" in row.status.text()
    assert len(book.get("p1")["texte"]) < TEXT_CHARS  # l'ancienne version, intacte


def test_long_breakouts_like_the_turtles_fit_in_the_rules():
    # Constaté : la cassure des 55 jours (Turtle Traders) = 1 320 bougies d'une heure, refusée
    import pytest

    from friday.trading.strategies.spec import MAX_PERIOD, SpecError, validate

    high = {"indicateur": "plus_haut", "periode": 1320}
    breakout = {
        **BREAKOUT,
        "achat": [{"gauche": {"indicateur": "cours"}, "op": ">", "droite": high}],
    }
    assert validate(breakout)["achat"][0]["droite"]["periode"] == 1320
    breakout["achat"][0]["droite"]["periode"] = MAX_PERIOD + 1
    with pytest.raises(SpecError, match="période hors limites"):
        validate(breakout)


def test_translator_notes_are_kept_whole_or_cut_between_words():
    from friday.trading.strategies.spec import short

    note = "Stop : le plan fixe 2 N, N étant l'ATR de 20 jours sur données journalières."
    assert short(note) == note
    cut = short("mot " * 200)
    assert cut.endswith("mot …") and len(cut) <= 402
