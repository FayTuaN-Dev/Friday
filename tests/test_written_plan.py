"""Le plan écrit devient la stratégie : traduit en règles par Claude (après aperçu), vérifié par
le code, exécuté par le moteur (backtest, alertes, check-list), choisi dans les réglages."""

import json

import pytest
from test_strategies import DAILY, RULES, finished_day, hourly_from, walk

from friday.trading.backtest.engine import simulate
from friday.trading.plan_rules import PlanRules
from friday.trading.plan_translate import TranslationError, parse
from friday.trading.strategies.custom import CustomStrategy
from friday.trading.strategies.plan import PlanStrategy
from friday.trading.strategies.spec import SpecError, describe, validate

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
