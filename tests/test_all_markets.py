"""Une stratégie sur tous les marchés à la fois (« compare Turtle sur tous les marchés ») :
les trades réunis en portefeuille, jugés comme sur un marché ; constaté : 8 trades Turtle
sur l'or ne prouvaient rien, seul l'ensemble des marchés peut le dire."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from friday.tools.strategies import CompareStrategiesTool, StrategyLab
from friday.tools.strategies_markets import asked_strategy
from friday.trading.backtest.compare import FAILED, PROMISING, WORKED, Result
from friday.trading.backtest.engine import Trade
from friday.trading.backtest.portfolio import UNIVERSE, portfolio
from friday.trading.backtest.report import Report
from friday.trading.instruments import by_symbol
from friday.trading.market import MarketUnavailable
from friday.trading.mode import strategy_request
from friday.trading.plan_book import PlanBook
from friday.trading.strategies import BY_NAME
from friday.trading.strategy_choice import StrategyChoice

START = datetime(2025, 1, 6, tzinfo=UTC)


def trades(results, start=START):
    return [Trade(start + timedelta(days=7 * i), "achat", 1, 0, None, closed=start + timedelta(
        days=7 * i + 2), result_r=r) for i, r in enumerate(results)]  # fmt: skip


def result(name, rs, start=START):
    found = trades(rs, start)
    return Result(BY_NAME[name], Report("x", found), (Report("a", found), Report("b", found)))


def test_a_few_trades_per_market_add_up_to_a_proven_portfolio():
    # 5 trades par marché : rien de prouvé seul ; 8 marchés ensemble : 40 trades, gagnant
    # sur les deux moitiés, au-delà du hasard
    each = [result("cassure", [2, -1, 2, 2, -1], START + timedelta(hours=k)) for k in range(8)]
    assert all(r.verdict == PROMISING for r in each)
    whole = portfolio(BY_NAME["cassure"], each)
    assert whole.report.count == 40 and whole.verdict == WORKED
    assert [t.closed for t in whole.report.trades] == sorted(t.closed for t in whole.report.trades)
    assert portfolio(BY_NAME["cassure"], []).verdict == FAILED  # aucun trade : rien à juger


def lab_with(tmp_path, markets):
    """{symbole : [résultats]} ; un symbole absent : historique indisponible."""
    trading = SimpleNamespace(rules_path=tmp_path / "r.json", alerts=None,
                              instrument_for=lambda q: by_symbol("XAUUSD"))  # fmt: skip
    lab = StrategyLab(trading)

    def results(instrument, only=None):
        if instrument.symbol not in markets:
            raise MarketUnavailable("Yahoo muet")
        return "du 06/01/2025 au 01/10/2026", markets[instrument.symbol]

    lab.results = results
    return lab


def test_one_strategy_on_every_market_names_the_best_and_the_worst(tmp_path):
    markets = {s: [result("cassure", [2, -1] * 3), result("repli", [-1, -1, 2])]
               for s in UNIVERSE[:6]}  # fmt: skip
    markets["XAUUSD"] = [result("cassure", [14, -1, -1]), result("repli", [-1])]
    markets["EURGBP"] = [result("cassure", [-1, -1, -1]), result("repli", [-1])]
    tool = CompareStrategiesTool(lab_with(tmp_path, markets), StrategyChoice(tmp_path / "s"))
    shown = tool.run(everything=True, strategy="cassure")
    text = shown.text
    assert "la cassure de range sur 8 marchés en même temps : 42 trades" in text
    assert "Le mieux : l'or (+12,00 R)" in text and "le moins bien : EUR/GBP (-3,00 R)" in text
    assert "Historique indisponible : " in text and "l'argent (métal)" in text
    items = shown.display.data["items"]
    assert items[0]["text"].endswith("Tous les marchés · la cassure de range")
    assert len(items) == 9  # le portefeuille, puis chaque marché


def test_all_strategies_on_every_market_warn_against_picking_the_lucky_one(tmp_path):
    markets = {"EURUSD": [result("cassure", [2, -1]), result("repli", [-1, -1])],
               "XAUUSD": [result("repli", [5]), result("cassure", [-1])]}  # fmt: skip
    tool = CompareStrategiesTool(lab_with(tmp_path, markets), StrategyChoice(tmp_path / "s"))
    shown = tool.run(everything=True)
    assert "Sur 2 marchés en même temps : " in shown.text
    assert "c'est souvent choisir celle qui a eu de la chance" in shown.text
    texts = [i["text"] for i in shown.display.data["items"]]
    assert any(t.endswith("l'or · le mieux : le repli sur moyenne (modèle)") for t in texts)


def test_a_plan_is_found_by_its_first_word_and_the_request_is_routed(tmp_path):
    book = PlanBook(tmp_path / "plans.json")
    plan = book.add("Turtle Traders", "Cassure des 55 jours")
    book.save_translation(
        plan["id"],
        {
            "nom": "Turtle",
            "achat": [
                {
                    "gauche": {"indicateur": "cours"},
                    "op": ">",
                    "droite": {"indicateur": "plus_haut", "periode": 20},
                }
            ],
        },
        "Cassure des 55 jours",
    )
    choice = StrategyChoice(tmp_path / "s.json", book)
    assert asked_strategy(choice, "", "compare Turtle sur tous les marchés") == f"plan:{plan['id']}"
    assert asked_strategy(choice, "cassure", "compare la cassure de range") == "cassure"
    assert asked_strategy(choice, "", "compare les stratégies") is None
    assert strategy_request("compare Turtle sur tous les marchés") == (
        "compare_strategies",
        {"instrument": "", "everything": True, "strategy": ""},
    )
    assert strategy_request("teste la cassure de range sur tous les marchés")[1]["strategy"] == (
        "cassure"
    )
    assert strategy_request("surveille tous les marchés") is None  # P2, pas une comparaison
