"""Les plans journaliers (Turtles) et les familles de marchés d'un plan. Constaté : Turtle
testé sur 2 ans de bougies 1 h donnait 8 trades sur l'or ; sur 20 ans de journées, il gagne
sur les matières et les indices et perd sur les devises depuis 2016 (d'où les familles)."""

from datetime import UTC, datetime, timedelta

from friday.trading.alerts.setup import announcement, detect, lasting
from friday.trading.backtest.compare import compare
from friday.trading.instruments import by_symbol
from friday.trading.market import Candle
from friday.trading.plan_book import PlanBook
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies.custom import CustomStrategy
from friday.trading.strategies.spec import describe, validate
from friday.trading.strategy_checks import signal

DAY0 = datetime(2020, 1, 6, tzinfo=UTC)
RULES = PlanRules(trend_ema=0, stop_atr=0, min_rr=0)


def turtle(**changes) -> dict:
    return validate({"nom": "Turtle", "unite": "jour", "heures": [9, 17],
                     "achat": [{"gauche": {"indicateur": "cours"}, "op": ">",
                                "droite": {"indicateur": "plus_haut", "periode": 20}}],
                     "stop": {"type": "atr", "multiple": 2}, "objectif": {"type": "aucun"},
                     "sortie": {"bougies": 10}} | changes)  # fmt: skip


def days(closes) -> list[Candle]:
    return [Candle(DAY0 + timedelta(days=i), c, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]


def test_a_daily_plan_is_said_in_days_and_has_no_hours():
    spec = turtle()
    assert spec["unite"] == "jour" and spec["heures"] is None
    lines = describe(spec)
    assert lines[0] == "Bougies : journalières (les périodes sont en jours)"
    assert "du plus haut des 20 jours précédents" in lines[1]
    assert "plus bas des 10 jours précédents" in lines[-1]
    assert validate({**spec, "unite": "n'importe quoi"})["unite"] == "heure"


def test_a_daily_plan_is_replayed_on_days_for_many_more_years():
    daily = days([100.0] * 30 + [100 + i for i in range(1, 40)] + [139 - 2 * i for i in range(20)])
    hourly = [Candle(daily[-1].time - timedelta(hours=48 - h), 100, 100.2, 99.8, 100)
              for h in range(48)]  # deux jours de bougies 1 h seulement  # fmt: skip
    (result,) = compare(hourly, daily, RULES, 0.0, (CustomStrategy(turtle()),))
    assert result.since == DAY0 and result.report.count == 1
    assert result.report.trades[0].result_r > 3  # la tendance suivie, en journées


def test_an_alert_comes_once_when_the_day_closes_not_every_hour():
    closes = [100.0] * 30 + [101.0]
    daily = days(closes) + [Candle(DAY0 + timedelta(days=31), 101, 101.5, 100.5, 101)]  # en cours
    strategy = CustomStrategy(turtle())
    morning = DAY0 + timedelta(days=31, hours=9)
    hourly = [Candle(morning - timedelta(hours=k), 101, 101.2, 100.8, 101) for k in range(3, 0, -1)]
    found = detect(hourly, daily, RULES, strategy)
    assert found is not None and found.bar.time == DAY0 + timedelta(days=30)
    assert not lasting(hourly, daily, RULES, strategy, found)  # nouveau : la veille, rien
    text = announcement(by_symbol("XAUUSD"), found, RULES, 0.0)
    assert "journée du 05/02 fermée à 101,0" in text and "des 10 jours précédents" in text
    from friday.trading.checklist import Idea, Market

    idea = Idea(by_symbol("XAUUSD"), "achat", 101.0, 99.0)
    check = signal(idea, Market(101.0, daily, hourly), morning, RULES, strategy)
    assert check.status == "ok" and "sur la dernière journée" in check.detail


def test_a_plan_follows_only_the_market_families_ticked(tmp_path):
    book = PlanBook(tmp_path / "plans.json")
    plan = book.add("Turtle", "Cassure des 20 jours")
    book.save_translation(plan["id"], turtle(), "Cassure des 20 jours")
    assert book.strategy(book.get(plan["id"])).covers(by_symbol("EURUSD"))  # tout par défaut
    book.set_families(plan["id"], ["matieres", "indices"])
    strategy = book.strategy(book.get(plan["id"]))
    assert strategy.covers(by_symbol("XAUUSD")) and strategy.covers(by_symbol("DAX"))
    assert not strategy.covers(by_symbol("EURUSD")) and not strategy.covers(by_symbol("BTCUSD"))
    book.save_translation(plan["id"], turtle(), "Cassure des 20 jours")  # retraduit : gardé
    assert book.get(plan["id"])["familles"] == ["matieres", "indices"]
    assert book.duplicate(plan["id"])["familles"] == ["matieres", "indices"]


def test_one_plan_on_all_markets_replays_only_it_and_only_its_markets(tmp_path):
    from types import SimpleNamespace

    from friday.tools.strategies import CompareStrategiesTool, StrategyLab
    from friday.trading.strategy_choice import StrategyChoice

    book = PlanBook(tmp_path / "plans.json")
    plan = book.add("Turtle", "Cassure des 20 jours")
    book.save_translation(plan["id"], turtle(), "Cassure des 20 jours")
    book.set_families(plan["id"], ["crypto"])
    choice = StrategyChoice(tmp_path / "s.json", book)
    read = []
    daily = days([100.0] * 30 + [100 + i for i in range(1, 40)])

    def history(instrument):
        read.append(instrument.symbol)
        return daily[-5:], daily

    trading = SimpleNamespace(rules_path=tmp_path / "r.json", alerts=None, choice=choice,
                              instrument_for=lambda q: None)  # fmt: skip
    lab = StrategyLab(trading, history)
    text = CompareStrategiesTool(lab, choice).run(everything=True, request="compare Turtle").text
    assert sorted(read) == ["BTCUSD", "ETHUSD"]  # les devises ne sont même pas lues
    assert "sur 2 marchés en même temps, en journalier depuis 2020" in text
    assert all(len(found) == 1 for _, _, found in lab._results.values())  # elle seule
