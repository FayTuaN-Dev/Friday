"""Le plan écrit devient la stratégie : traduit en règles par Claude (après aperçu), vérifié par
le code, exécuté par le moteur (backtest, alertes, check-list), choisi dans les réglages."""

import json
import time

import pytest
from test_strategies import DAILY, RULES, finished_day, hourly_from, walk

from friday.tools.plan_translate import TranslatePlanTool
from friday.trading.backtest.engine import simulate
from friday.trading.journal import TradeJournal
from friday.trading.mode import strategy_request
from friday.trading.plan_rules import PlanRules
from friday.trading.plan_translate import TranslationError, parse
from friday.trading.strategies.custom import CustomStrategy
from friday.trading.strategies.plan import PlanStrategy
from friday.trading.strategies.spec import SpecError, describe, validate
from friday.trading.strategy_choice import DEFAULT, StrategyChoice

COURS, EMA50, RSI = {"indicateur": "cours"}, {"indicateur": "ema", "periode": 50}, {
    "indicateur": "rsi", "periode": 14}  # fmt: skip
REPLI = {  # le modèle « repli », écrit comme Claude le traduirait
    "nom": "Mon plan", "resume": "repli sur l'EMA50 en tendance", "tendance": {"ema": 50},
    "achat": [{"gauche": COURS, "op": "proche", "droite": EMA50, "k": 1},
              {"gauche": RSI, "op": ">=", "droite": {"valeur": 40}},
              {"gauche": RSI, "op": "<=", "droite": {"valeur": 50}},
              {"gauche": RSI, "op": "monte"}],
    "vente": [{"gauche": COURS, "op": "proche", "droite": EMA50, "k": 1},
              {"gauche": RSI, "op": ">=", "droite": {"valeur": 50}},
              {"gauche": RSI, "op": "<=", "droite": {"valeur": 60}},
              {"gauche": RSI, "op": "baisse"}],
    "stop": {"type": "creux", "bougies": 10}, "objectif": {"type": "r", "valeur": 2},
    "non_traduit": ["2 trades ouverts au plus : gestion du risque"],
}  # fmt: skip
BREAKOUT = {"tendance": None, "stop": {"type": "atr", "multiple": 2},
            "achat": [{"gauche": COURS, "op": ">", "droite": {"indicateur": "plus_haut",
                                                              "periode": 24}}],
            "objectif": {"type": "r", "valeur": 3}, "heures": [9, 17]}  # fmt: skip


def test_rules_are_checked_before_use():
    spec = validate(REPLI)
    assert spec["stop"] == {"type": "creux", "bougies": 10} and len(spec["vente"]) == 4
    for broken, message in (
        ({"achat": []}, "aucune condition"),
        ({"achat": [{"op": "magie"}]}, "opérateur inconnu"),
        ({"achat": [{"gauche": {"indicateur": "astrologie"}, "op": ">", "droite": COURS}]},
         "indicateur inconnu"),
        ({"achat": [{"gauche": {"indicateur": "ema", "periode": 9999}, "op": ">",
                     "droite": COURS}]}, "période hors limites"),
        ({"achat": [{"gauche": COURS, "op": ">", "droite": {"valeur": "haut"}}]}, "non numérique"),
        ({"achat": [{"gauche": COURS, "op": ">", "droite": COURS}],
          "stop": {"multiple": "deux"}}, "mal formée"),
        ("du texte", "pas un objet JSON"),
    ):  # fmt: skip
        with pytest.raises(SpecError, match=message):
            validate(broken)


def test_friday_says_what_it_understood_in_french():
    lines = describe(validate(BREAKOUT))
    assert lines[0] == ("Achat quand : le cours (clôture) est au-dessus du plus haut des 24 "
                        "bougies précédentes")  # fmt: skip
    assert lines[1:] == [
        "Stop : 2 ATR",
        "Objectif : 3 fois le risque",
        "Heures : entrées sur les bougies qui ferment entre 9 h et 17 h (Paris)",
    ]
    assert describe(validate(REPLI))[-1] == "À noter : 2 trades ouverts au plus : gestion du risque"


def test_the_written_plan_trades_exactly_like_the_same_rules_built_in():
    hourly = walk(n=1500, seed=11)
    rules = PlanRules(trend_ema=50)
    model = simulate(hourly, DAILY, rules, 0.05, PlanStrategy())
    written = simulate(hourly, DAILY, rules, 0.05, CustomStrategy(validate(REPLI)))
    key = lambda t: (t.opened, t.direction, round(t.stop, 9), round(t.target, 9))  # noqa: E731
    assert len(model) > 5 and [key(t) for t in model] == [key(t) for t in written]


def test_the_written_plan_never_sees_the_future():
    strategy = CustomStrategy(validate({**BREAKOUT, "heures": None, "vente": [
        {"gauche": COURS, "op": "croise_en_dessous", "droite": EMA50}]}))  # fmt: skip
    hourly, seen = walk(n=500, seed=5), 0
    full = strategy.prepare(hourly, DAILY, RULES)
    for i in range(60, 400):
        day = finished_day(DAILY, hourly[i].time)
        cut = strategy.prepare(hourly[: i + 1], DAILY, RULES)
        assert strategy.entry(full, i, day) == strategy.entry(cut, i, day), i
        seen += strategy.entry(full, i, day) is not None
    assert seen > 0


def test_hours_and_indicator_targets():
    flat = [100 + (0.05 if i % 2 else -0.05) for i in range(80)]
    hourly = hourly_from(flat + [101.0])  # dernière bougie : ferme à 10 h UTC = 12 h à Paris
    strategy = CustomStrategy(validate(BREAKOUT))
    state = strategy.prepare(hourly, DAILY, RULES)
    entry = strategy.entry(state, len(hourly) - 1, finished_day(DAILY, hourly[-1].time))
    assert entry.side == "achat" and entry.target == pytest.approx(101 + 3 * (101 - entry.stop))
    night = CustomStrategy(validate({**BREAKOUT, "heures": [14, 17]}))
    assert night.entry(night.prepare(hourly, DAILY, RULES), len(hourly) - 1, -1) is None
    to_mean = CustomStrategy(validate({**BREAKOUT, "objectif": {"type": "indicateur",
                                                                "indicateur": EMA50}}))  # fmt: skip
    state = to_mean.prepare(hourly, DAILY, RULES)
    assert to_mean.entry(state, len(hourly) - 1, -1) is None  # la moyenne est sous l'entrée


def test_claude_answer_is_parsed_strictly():
    good = "```json\n" + json.dumps(BREAKOUT) + "\n```"
    assert parse(good)["objectif"] == {"type": "r", "valeur": 3.0}
    assert parse("Voici : " + json.dumps(BREAKOUT) + " Bonne journée.")["heures"] == [9, 17]
    for answer, message in (("Je ne peux pas.", "pas renvoyé"), ("{pas du json}", "illisibles"),
                            (json.dumps({"achat": []}), "invalides")):  # fmt: skip
        with pytest.raises(TranslationError, match=message):
            parse(answer)


def test_choice_follows_the_written_plan_once_translated(tmp_path):
    choice = StrategyChoice(tmp_path / "s.json", tmp_path / "rules.json")
    assert choice.get("XAUUSD").name == "repli" and choice.translated() is None
    choice.save_translation(REPLI, "Mon plan : repli sur l'EMA50.")
    assert choice.get("XAUUSD").name == "mon_plan"  # par défaut : ton plan écrit
    assert [s.name for s in choice.available()][:2] == ["mon_plan", "repli"]
    assert not choice.outdated("Mon plan : repli sur l'EMA50.")
    assert choice.outdated("Mon plan : cassure du range.")  # modifié depuis
    choice.set(DEFAULT, "cassure")
    assert choice.get("EURUSD").name == "cassure"


class Job:
    def __init__(self, answer, ok=True):
        self.answer, self.ok, self.task, self.sent = answer, ok, None, []

    @property
    def busy(self):
        return False

    def run(self, content, options=None):
        self.sent.append(content)
        return {"ok": self.ok, "result": self.answer}


def make_tool(tmp_path, answer, plan="Entrée : cassure du plus haut de 24 h. Compte de 5 000 €."):
    tmp_path.mkdir(parents=True, exist_ok=True)
    plan_path = tmp_path / "plan.txt"
    if plan:
        plan_path.write_text(plan, "utf-8")
    choice, done = StrategyChoice(tmp_path / "s.json", tmp_path / "rules.json"), []
    tool = TranslatePlanTool(plan_path, choice, Job(answer), TradeJournal(tmp_path / "t.db"),
                             lambda task, result: done.append(result))  # fmt: skip
    return tool, choice, done


def wait(items):
    for _ in range(100):
        if items:
            return
        time.sleep(0.02)


def test_translation_goes_through_the_preview_then_becomes_the_strategy(tmp_path):
    tool, choice, done = make_tool(tmp_path, json.dumps(BREAKOUT))
    assert "j'envoie ?" in tool.confirmation({})
    packet = tool.preview({})
    assert "5 000" not in packet.items[0].text and "montant" in packet.masked  # masqué
    assert "Rien n'a été envoyé" in tool.run().text  # sans validation : rien ne part
    tool.confirmation({})
    tool.preview({}).approved = True
    assert "C'est envoyé" in tool.run().text
    wait(done)
    assert choice.custom() is not None and choice.get("XAUUSD").name == "mon_plan"
    assert "Ton plan est traduit en règles : Achat quand" in done[0].text
    assert done[0].display.data["items"][0]["text"] == "Achat quand"


def test_a_bad_translation_changes_nothing(tmp_path):
    tool, choice, done = make_tool(tmp_path, "Désolé, je ne sais pas.")
    tool.confirmation({})
    tool.preview({}).approved = True
    tool.run()
    wait(done)
    assert "La traduction de ton plan a échoué" in done[0].text and choice.translated() is None
    empty, _, _ = make_tool(tmp_path / "e", "{}", plan="")
    assert empty.confirmation({}) is None and "plan de trading est vide" in empty.run().text


def test_translation_is_launched_by_the_code():
    assert strategy_request("traduis mon plan") == ("translate_plan", {})
    assert strategy_request("mets à jour les règles de mon plan") == ("translate_plan", {})


def test_settings_show_the_choice_and_what_was_understood(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.trading_plan import NOT_YET, TradingPlanRow
    from friday.ui.desktop.settings.trading_strategy import StrategyRow

    QApplication.instance() or QApplication([])
    choice = StrategyChoice(tmp_path / "s.json", tmp_path / "rules.json")
    asked = []
    plan_path = tmp_path / "plan.txt"
    row = TradingPlanRow(plan_path, choice, lambda: asked.append(True))
    assert row.rules.text() == NOT_YET
    row.editor.setPlainText("Cassure du plus haut de 24 h.")
    row._translate()
    assert (
        asked == [True] and plan_path.read_text("utf-8").strip() == "Cassure du plus haut de 24 h."
    )
    choice.save_translation(BREAKOUT, "Cassure du plus haut de 24 h.")
    row.refresh_rules()
    assert row.rules.text().startswith("✅ Traduit le") and "plus haut des 24" in row.rules.text()
    row.editor.setPlainText("Autre chose.")
    row.refresh_rules()
    assert row.rules.text().startswith("⚠️ Plan modifié")
    strategies = StrategyRow(choice)
    strategies.box.setCurrentIndex(strategies.box.findData("retour"))
    assert choice.get("XAUUSD").name == "retour"
    assert not TradingPlanRow(None).translate_button.isEnabled()
