"""Bibliothèque de stratégies (T7) : aucune ne voit le futur, chacune se déclenche sur son
cas d'école, verdicts honnêtes, choix par instrument suivi par alertes, check-list, briefing."""

import random
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from friday.tools.strategies import ChooseStrategyTool, CompareStrategiesTool, StrategyLab
from friday.trading.backtest.compare import FAILED, PROMISING, WORKED, Result, compare
from friday.trading.backtest.engine import Trade
from friday.trading.backtest.report import Report
from friday.trading.instruments import by_symbol
from friday.trading.market import Candle
from friday.trading.mode import TradingMode, strategy_request
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies import BY_NAME, STRATEGIES, finished_day, strategy_named
from friday.trading.strategy_choice import StrategyChoice

START = datetime(2026, 6, 1, tzinfo=UTC)  # un lundi


def walk(n=900, seed=7, start=START, step=1.0):
    rng = random.Random(seed)
    price, candles = 100.0, []
    for i in range(n):
        move = rng.gauss(0, step)
        high, low = max(price, price + move) + abs(rng.gauss(0, 0.3)), min(price, price + move)
        candles.append(Candle(start + timedelta(hours=i), price, high,
                              low - abs(rng.gauss(0, 0.3)), price + move))  # fmt: skip
        price += move
    return candles


DAILY = [Candle(START - timedelta(days=300 - d), 80 + d * 0.05, 81 + d * 0.05, 79 + d * 0.05,
                80 + d * 0.05) for d in range(300)]  # fmt: skip
RULES = PlanRules(trend_ema=50)


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_no_strategy_ever_sees_the_future(strategy):
    hourly = walk()
    full = strategy.prepare(hourly, DAILY, RULES)
    seen = 0
    for i in range(60, 420):
        day = finished_day(DAILY, hourly[i].time)
        cut = strategy.prepare(hourly[: i + 1], DAILY, RULES)
        assert strategy.entry(full, i, day) == strategy.entry(cut, i, day), (strategy.name, i)
        seen += strategy.entry(full, i, day) is not None
    assert seen > 0  # la stratégie a bien eu des signaux à comparer


def hourly_from(closes, start=START, wick=0.2):
    return [Candle(start + timedelta(hours=i), c, c + wick, c - wick, c)
            for i, c in enumerate(closes)]  # fmt: skip


def last_entry(name, hourly, rules=RULES):
    strategy = BY_NAME[name]
    state = strategy.prepare(hourly, DAILY, rules)
    i = len(hourly) - 1
    return strategy.entry(state, i, finished_day(DAILY, hourly[i].time))


def test_each_family_fires_on_its_textbook_case():
    flat = [100 + (0.05 if i % 2 else -0.05) for i in range(80)]
    # cassure : une clôture au-dessus du plus haut des 20 dernières heures, tendance haussière
    breakout = last_entry("cassure", hourly_from(flat + [101.0]))
    assert breakout.side == "achat" and breakout.stop < 101 < breakout.target
    # croisement : l'EMA20 repasse au-dessus de l'EMA50 après une baisse
    down_up = [100 - 0.1 * i for i in range(60)] + [94 + 0.4 * i for i in range(1, 30)]
    hourly = hourly_from(down_up)
    signals = [last_entry("croisement", hourly[: k + 1]) for k in range(60, len(hourly))]
    assert [e.side for e in signals if e] == ["achat"]  # une seule fois, au croisement
    # retour à la moyenne : chute brutale (RSI < 30, sous la bande basse) → achat vers la moyenne
    reversion = last_entry("retour", hourly_from(flat + [99.0, 98.0, 97.0]))
    assert reversion.side == "achat" and 97.0 < reversion.target < 100.1
    # Londres : nuit calme entre 99,8 et 100,2, cassure à 8 h (heure de Londres = 7 h UTC)
    night = [100 + (0.1 if i % 2 else -0.1) for i in range(31)]  # lundi 0 h → mardi 6 h UTC
    london = last_entry("londres", hourly_from(night + [100.6], wick=0.05))
    assert london.side == "achat" and london.stop <= 99.95


def report(results):
    return Report("x", [Trade(START, "achat", 1, 0, 2, result_r=r) for r in results])


def test_verdicts_are_honest():
    good = Result(BY_NAME["cassure"], report([2, -1, 2, 2, -1] * 8),
                  (report([2, -1, 2]), report([2, -1, 2])))  # fmt: skip
    assert good.verdict == WORKED and good.why() == ""
    lucky = Result(BY_NAME["cassure"], report([2, -1, 2, 2, -1] * 8),
                   (report([2, 2, 2]), report([-1, -1, 2, -1, -1])))  # fmt: skip
    assert lucky.verdict == PROMISING and lucky.why() == "perdante sur une moitié de la période"
    few = Result(BY_NAME["cassure"], report([2, -1, 2]), (report([2]), report([-1, 2])))
    assert few.verdict == PROMISING and few.why() == "trop peu de trades (3)"
    noisy = Result(BY_NAME["cassure"], report([2, -1, -1] * 20 + [2]),
                   (report([2, -1]), report([2, -1])))  # fmt: skip
    assert noisy.verdict == PROMISING and noisy.why() == "gain dans la marge du hasard"
    assert Result(BY_NAME["repli"], report([-1, 2, -1, -1]), (report([]), report([]))).verdict \
        == FAILED  # fmt: skip


def test_compare_runs_every_strategy_on_the_same_data():
    hourly = walk(n=1200, seed=3)
    results = compare(hourly, DAILY, RULES, spread=0.05)
    assert {r.strategy.name for r in results} == set(BY_NAME)
    order = {WORKED: 0, PROMISING: 1, FAILED: 2}
    assert [order[r.verdict] for r in results] == sorted(order[r.verdict] for r in results)
    for r in results:
        assert r.halves[0].count + r.halves[1].count == r.report.count


def test_choice_is_kept_per_instrument(tmp_path):
    choice = StrategyChoice(tmp_path / "s.json")
    assert choice.get("XAUUSD").name == "repli"  # plan écrit pas encore traduit : le modèle
    choice.set("XAUUSD", "londres")
    choice.set("EURUSD", "cassure")
    choice.set("_defaut", "retour")
    again = StrategyChoice(tmp_path / "s.json")
    assert again.get("XAUUSD").name == "londres" and again.get("EURUSD").name == "cassure"
    assert again.get("GBPUSD").name == "retour"  # sans choix propre : celui par défaut
    (tmp_path / "s.json").write_text("{abîmé", "utf-8")
    assert StrategyChoice(tmp_path / "s.json").get("XAUUSD").name == "repli"


def test_strategies_are_recognized_by_the_code():
    assert strategy_named("la cassure de range") == "cassure"
    assert strategy_named("la cassure de l'ouverture de Londres") == "londres"
    assert strategy_named("retour à la moyenne") == "retour"
    assert strategy_named("rien de connu") is None
    assert strategy_request("compare les stratégies sur l'or") == (
        "compare_strategies",
        {"instrument": "XAUUSD", "everything": False, "strategy": ""})  # fmt: skip
    assert strategy_request("quelle stratégie marche sur tous mes instruments ?") == (
        "compare_strategies", {"instrument": "", "everything": True, "strategy": ""})  # fmt: skip
    assert strategy_request("choisis la cassure de range pour l'or") == (
        "choose_strategy", {"strategy": "cassure", "instrument": "XAUUSD"})  # fmt: skip
    assert strategy_request("reviens à mon plan sur l'EUR/USD")[1]["strategy"] == "mon_plan"
    assert strategy_request("que penses-tu de l'or ?") is None
    assert TradingMode().route("compare les stratégies sur l'or") == "local"


def lab_with(tmp_path, verdicts):
    """Un laboratoire aux résultats choisis : {nom : verdict}."""
    reports = {WORKED: [2, -1, 2, 2, -1] * 8, PROMISING: [2, -1, 2], FAILED: [-1, -1, 2, -1]}
    trading = SimpleNamespace(rules_path=tmp_path / "r.json", instrument_for=lambda q: by_symbol(
        "XAUUSD"), alerts=None)  # fmt: skip
    lab = StrategyLab(trading)
    results = [
        Result(BY_NAME[n], report(reports[v]), (report(reports[v][:3]), report(reports[v][:3])))
        for n, v in verdicts.items()
    ]
    lab.results = lambda instrument: ("du 01/06/2026 au 01/09/2026", results)
    return lab, StrategyChoice(tmp_path / "s.json")


def test_compare_tool_says_what_worked_and_what_did_not(tmp_path):
    lab, choice = lab_with(tmp_path, {"cassure": WORKED, "londres": PROMISING, "repli": FAILED})
    text = CompareStrategiesTool(lab, choice).run("or").text
    assert "a fonctionné : la cassure de range (+0,80 R par trade sur 40 trades" in text
    assert "prometteuses mais pas prouvées : la cassure de l'ouverture de Londres" in text
    assert "n'ont pas fonctionné : le repli sur moyenne (modèle)" in text
    assert "ta stratégie actuelle : le repli sur moyenne (modèle) (n'a pas fonctionné)" in text


def test_a_strategy_that_failed_is_refused_and_a_promising_one_comes_with_a_warning(tmp_path):
    lab, choice = lab_with(tmp_path, {"cassure": FAILED, "londres": PROMISING, "repli": FAILED})
    tool = ChooseStrategyTool(lab, choice)
    assert "Je ne la mets pas" in tool.run("cassure", "or").text
    assert choice.get("XAUUSD").name == "repli"
    accepted = tool.run("londres", "or").text
    assert "suivent maintenant la cassure de l'ouverture de Londres" in accepted
    assert "seulement prometteuse (trop peu de trades (3))" in accepted
    assert choice.get("XAUUSD").name == "londres"
    assert "n'est encore traduit" in tool.run("mon plan", "or").text
    assert "Je ne connais pas cette stratégie" in tool.run("martingale", "or").text


def test_alerts_checklist_and_briefing_follow_the_chosen_strategy():
    from friday.trading.alerts.setup import announcement, detect
    from friday.trading.checklist import Idea, Market
    from friday.trading.strategy_checks import signal

    flat = [100 + (0.05 if i % 2 else -0.05) for i in range(80)]
    hourly = hourly_from(flat + [101.0])
    found = detect(hourly, DAILY, RULES, BY_NAME["cassure"])
    assert found.side == "achat"
    text = announcement(by_symbol("EURUSD"), found, RULES, 0.0)
    assert text.startswith("Alerte setup « la cassure de range » sur EUR/USD : achat")
    now = hourly[-1].time + timedelta(hours=1, minutes=5)
    market = Market(101.0, DAILY, hourly)
    buy = Idea(by_symbol("EURUSD"), "achat", 101.0, 100.5)
    assert signal(buy, market, now, RULES, BY_NAME["cassure"]).status == "ok"
    sell = Idea(by_symbol("EURUSD"), "vente", 101.0, 101.5)
    assert signal(sell, market, now, RULES, BY_NAME["cassure"]).status == "ko"
    later = now + timedelta(hours=5)  # le signal a plus de 3 h : il ne compte plus
    assert signal(buy, Market(101.0, DAILY, hourly + hourly_from(
        [101.0] * 5, hourly[-1].time + timedelta(hours=1))), later, RULES,
        BY_NAME["cassure"]).status == "ko"  # fmt: skip
