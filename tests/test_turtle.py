"""Les règles « Turtle fidèle » : sortie suiveuse (cassure inverse), pas d'objectif fixe, stop
en ATR de journées (le « 2 N »). Constaté : sans elles, Turtle Traders était testé avec un
objectif à 2 R (il coupe les grosses tendances) et un stop 2 ATR d'une heure (5 fois trop
serré)."""

from datetime import UTC, datetime, timedelta

import pytest

from friday.trading.backtest.engine import Trade, _exit, simulate
from friday.trading.market import Candle
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies.custom import CustomStrategy
from friday.trading.strategies.spec import SpecError, describe, validate

START = datetime(2026, 1, 5, tzinfo=UTC)
NO_RISK_RULES = PlanRules(trend_ema=0, stop_atr=0, min_rr=0)  # seules les règles du plan


def turtle(**changes) -> dict:
    spec = {"nom": "Turtle", "resume": "Cassure des 20 bougies",
            "achat": [{"gauche": {"indicateur": "cours"}, "op": ">",
                       "droite": {"indicateur": "plus_haut", "periode": 20}}],
            "vente": [], "stop": {"type": "atr", "multiple": 2},
            "objectif": {"type": "aucun"}, "sortie": {"bougies": 10}}  # fmt: skip
    return validate(spec | changes)


def candles(closes: list[float], spread: float = 0.5) -> list[Candle]:
    return [Candle(START + timedelta(hours=i), c, c + spread, c - spread, c)
            for i, c in enumerate(closes)]  # fmt: skip


def test_the_new_rules_are_checked_and_said_in_french():
    spec = turtle(stop={"type": "atr", "multiple": 2, "journalier": True, "periode": 20})
    assert spec["sortie"] == {"bougies": 10} and spec["objectif"] == {"type": "aucun"}
    lines = describe(spec)
    assert "Stop : 2 ATR journaliers (ATR des 20 derniers jours)" in lines
    assert "Objectif : aucun, on laisse courir la tendance" in lines
    assert any(
        line.startswith("Sortie : à la cassure du plus bas des 10 bougies") for line in lines
    )
    with pytest.raises(SpecError, match="sans sortie"):
        turtle(sortie=None)  # sans objectif ni sortie, un trade ne finirait jamais
    old = validate({**turtle(), "objectif": {"type": "r", "valeur": 2}, "sortie": None})
    assert old["sortie"] is None and "Sortie" not in " ".join(describe(old))  # comme avant


def test_a_trend_is_ridden_until_the_reverse_breakout_instead_of_cut_at_2r():
    # Plat, cassure, longue montée, puis chute : la sortie suiveuse garde presque toute la
    # tendance ; un objectif à 2 R l'aurait coupée tôt
    closes = [100.0] * 30 + [100 + i for i in range(1, 61)] + [160 - 3 * i for i in range(1, 15)]
    hourly = candles(closes)
    riding = simulate(hourly, [], NO_RISK_RULES, strategy=CustomStrategy(turtle()))
    capped = simulate(hourly, [], NO_RISK_RULES, strategy=CustomStrategy(
        turtle(objectif={"type": "r", "valeur": 2}, sortie=None)))  # fmt: skip
    assert riding[0].result_r > 5 * capped[0].result_r > 0
    assert riding[0].closed > START + timedelta(hours=90)  # sorti dans la chute, pas avant


def test_the_trailing_exit_only_tightens_and_never_loosens_the_stop():
    trade = Trade(START, "achat", entry=100, stop=96, target=None, trail=10)
    bar = Candle(START, 97, 98, 96.5, 97.5)  # touche 96,5 : au-dessus du stop
    assert not _exit(trade, bar, 0.0, trail=90.0)  # sortie plus loin que le stop : le stop reste
    assert _exit(trade, bar, 0.0, trail=97.0) and trade.result_r == pytest.approx(-0.75)


def test_the_two_n_stop_uses_days_not_hours():
    # Une heure bouge peu, une journée beaucoup : le stop « 2 N » est bien plus large
    hourly = candles([100.0] * 30 + [101.0], spread=0.2)
    daily = [Candle(START - timedelta(days=30 - d), 100, 103, 97, 100) for d in range(25)]
    strategy = CustomStrategy(turtle(stop={"type": "atr", "multiple": 2, "journalier": True,
                                           "periode": 20}))  # fmt: skip
    state = strategy.prepare(hourly, daily, NO_RISK_RULES)
    entry = strategy.entry(state, 30, len(daily) - 1)
    assert entry is not None and entry.target is None and entry.trail == 10
    assert 101 - entry.stop == pytest.approx(12.0, rel=0.05)  # 2 × ATR journalier (~6)
    hourly_entry = CustomStrategy(turtle()).entry(
        CustomStrategy(turtle()).prepare(hourly, daily, NO_RISK_RULES), 30, len(daily) - 1
    )
    assert 101 - hourly_entry.stop < 2  # 2 ATR d'une heure : serré


def test_an_alert_without_target_says_how_it_will_exit():
    from friday.trading.alerts.setup import Setup, announcement
    from friday.trading.instruments import OTHERS

    gold = OTHERS["XAUUSD"]
    setup = Setup("achat", Candle(START, 100, 101, 99, 100.5), None, 1.0, 55, 50, 96.0, None,
                  CustomStrategy(turtle()), trail=480)  # fmt: skip
    text = announcement(gold, setup, NO_RISK_RULES, 0.0)
    assert "pas d'objectif : sortie à la cassure du plus bas des 480 bougies" in text
