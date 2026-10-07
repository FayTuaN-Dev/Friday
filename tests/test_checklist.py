"""Check-list avant trade (T1) : les règles du plan vérifiées par le code, règle par règle."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from friday.tools.trade_check import TradeCheckTool
from friday.trading import Trading
from friday.trading.calendar import Event
from friday.trading.checklist import KO, OK, UNKNOWN, Context, Idea, Market
from friday.trading.instruments import by_symbol
from friday.trading.journal import TradeJournal
from friday.trading.market import Candle, ema
from friday.trading.mode import TradingMode
from friday.trading.plan_checks import evaluate
from friday.trading.plan_rules import PlanRules, load_rules, save_rules

GOLD = by_symbol("XAUUSD")
NOW = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)  # 11 h à Paris


def bars(closes, hours=1):
    start = datetime(2026, 9, 1, tzinfo=UTC)
    return [Candle(start + timedelta(hours=i * hours), c, c + 5, c - 5, c)
            for i, c in enumerate(closes)]  # fmt: skip


def hourly_pullback():
    """Hausse, puis repli en dents de scie : RSI 1 h ≈ 48 qui remonte (44 avant), EMA50 1 h
    ≈ 4 276, ATR 1 h = 10, dernier cours 4 283,5."""
    closes = [4100 + 2 * i for i in range(100)]
    for i in range(30):
        closes.append(closes[-1] + (-3 if i % 2 == 0 else 2))
    closes[-1] = closes[-2] + 2.5
    return bars(closes)


def market(**changes):
    daily = bars([3000 + 4 * i for i in range(300)], hours=24)  # EMA200 bien sous le cours
    return replace(Market(4283.5, daily, hourly_pullback()), **changes)


def context(**changes):
    return replace(Context(NOW, events=[], open_trades=0, value_per_lot=10.0, account="USD"),
                   **changes)  # fmt: skip


def statuses(verdict):
    return {c.rule.split(" ")[0]: c.status for c in verdict.checks}


def good_buy(**changes):
    return replace(Idea(GOLD, "achat", 4280, 4260, 4320, risk_percent=1), **changes)


def test_ema_is_seeded_by_the_simple_average():
    assert ema([1, 2, 3], 3) == 2 and ema([1, 2], 3) is None
    assert ema([1, 2, 3, 4], 3) == pytest.approx(3.0)


def test_green_light_when_every_rule_of_the_plan_holds():
    verdict = evaluate(good_buy(), market(), context(), PlanRules())
    assert verdict.light == "vert", verdict.text()
    assert len(verdict.checks) == 8 and {c.status for c in verdict.checks} == {OK}
    assert verdict.text().startswith("🟢 Feu vert")
    assert "RSI 47,7 (avant : 43,7, il remonte)" in verdict.text()


def test_red_light_names_each_broken_rule():
    sell = Idea(GOLD, "vente", 4280, 4300, 4240, risk_percent=2)
    verdict = evaluate(sell, market(), context(open_trades=2), PlanRules())
    found = statuses(verdict)
    assert found["Tendance"] == KO and "contre-tendance" in verdict.text()
    assert found["RSI"] == KO  # zone miroir 50–60 à la vente
    assert found["Risque"] == KO and found["Au"] == KO
    assert verdict.light == "rouge" and verdict.text().startswith("🔴 Feu rouge : 4 règle(s)")
    assert verdict.spoken().startswith("Feu rouge : règles enfreintes : Tendance (EMA200")


def test_tight_stop_far_entry_and_small_target_are_refused():
    idea = good_buy(entry=4310, stop=4305, target=4315)  # stop 0,5 ATR, à 3 ATR de l'EMA, 1 R
    found = statuses(evaluate(idea, market(), context(), PlanRules()))
    assert found["Stop"] == KO and found["Repli"] == KO and found["Objectif"] == KO


def test_orange_light_says_what_is_missing_and_where_the_target_would_be():
    idea = good_buy(target=None, risk_percent=None)
    verdict = evaluate(idea, market(), context(), PlanRules())
    assert verdict.light == "orange"
    assert "à 2 R il serait à 4 320,00" in verdict.text()
    assert "capital inconnu" in verdict.text()


def test_risk_is_checked_from_capital_and_lots():
    rules = PlanRules(capital=10_000)  # 1 % = 100 USD ; 20 $ de stop = 2 000 USD par lot
    sized = evaluate(good_buy(risk_percent=None), market(), context(), rules)
    assert "au plus 0,05 lot(s)" in sized.text() and sized.light == "vert"
    big = evaluate(good_buy(risk_percent=None, lots=0.1), market(), context(), rules)
    assert statuses(big)["Risque"] == KO and "2,00 % du capital" in big.text()


def test_strong_news_soon_blocks_but_later_news_is_only_mentioned():
    soon = Event(NOW + timedelta(minutes=20), "USD", "Non-Farm Employment Change", "High", "", "")
    later = Event(NOW + timedelta(hours=3), "USD", "FOMC Minutes", "High", "", "")
    other = Event(NOW + timedelta(minutes=10), "JPY", "BoJ Rate", "High", "", "")
    blocked = evaluate(good_buy(), market(), context(events=[soon, later]), PlanRules())
    assert statuses(blocked)["Pas"] == KO and "Non-Farm" in blocked.text() and "20 min" in (
        blocked.text())  # fmt: skip
    calm = evaluate(good_buy(), market(), context(events=[later, other]), PlanRules())
    assert statuses(calm)["Pas"] == OK and "FOMC Minutes à 14:00" in calm.text()
    down = evaluate(good_buy(), market(), context(events=None), PlanRules())
    assert statuses(down)["Pas"] == UNKNOWN


def test_rules_set_to_zero_are_skipped_and_missing_market_is_said():
    rules = PlanRules(trend_ema=0, pullback_ema=0, stop_atr=0, min_rr=0, max_risk=0, max_open=0,
                      news_minutes=0)  # fmt: skip
    verdict = evaluate(good_buy(), market(), context(), rules)
    assert [c.rule.split(" ")[0] for c in verdict.checks] == ["RSI"]
    blind = evaluate(good_buy(), None, context(), PlanRules())
    assert statuses(blind)["Données"] == UNKNOWN and blind.light == "orange"


def test_futures_without_visible_chart_compare_the_current_price():
    verdict = evaluate(good_buy(entry=4150, stop=4130, target=4190), market(shift_known=False),
                       context(), PlanRules())  # fmt: skip
    pullback = next(c for c in verdict.checks if c.rule.startswith("Repli"))
    assert pullback.status == OK and "cours actuel" in pullback.detail
    shifted = evaluate(good_buy(), market(shift=28.0), context(), PlanRules())
    assert "cours 4 255,50" in shifted.text()  # niveaux recalés sur le graphique


def test_stop_or_target_on_the_wrong_side_is_an_error():
    with pytest.raises(ValueError, match="stop doit être sous"):
        evaluate(good_buy(stop=4300), market(), context(), PlanRules())
    with pytest.raises(ValueError, match="objectif doit être au-dessus"):
        evaluate(good_buy(target=4200), market(), context(), PlanRules())


def test_rules_are_saved_and_a_broken_file_gives_the_defaults(tmp_path):
    path = tmp_path / "rules.json"
    assert load_rules(path) == PlanRules()
    save_rules(path, PlanRules(min_rr=3, capital=5000))
    assert load_rules(path).min_rr == 3 and load_rules(path).capital == 5000
    path.write_text("{abîmé", "utf-8")
    assert load_rules(path) == PlanRules()


def make_check_tool(tmp_path, events=(), fail_market=False):
    from friday.trading.market import MarketUnavailable

    journal = TradeJournal(tmp_path / "t.db")
    builder = SimpleNamespace(context=SimpleNamespace(events=lambda: (list(events), None)))
    trading = Trading(TradingMode(), journal, builder, None, "USD",
                      rules_path=tmp_path / "rules.json")  # fmt: skip

    def load(instrument, chart):
        if fail_market:
            raise MarketUnavailable("Yahoo en panne.")
        return market()

    return TradeCheckTool(trading, market=load, now=lambda: NOW), journal


def test_tool_shows_the_checklist_and_reads_the_saved_rules(tmp_path):
    tool, journal = make_check_tool(tmp_path)
    result = tool.run("achat", 4280, 4260, "l'or", 4320, 1)
    assert "« Feu vert : toutes les règles de ton plan sont respectées. »" in result.text
    assert result.display.kind == "items" and result.display.data["icon"] == "🚦"
    assert result.display.data["items"][0]["text"].startswith("🟢")
    journal.open_trade("XAUUSD", "achat", 4200, 4180)
    save_rules(tmp_path / "rules.json", PlanRules(max_open=1))
    red = tool.run("achat", 4280, 4260, "or", 4320, 1).text
    assert "« Feu rouge : règle enfreinte : Au plus 1 trade(s) ouvert(s). »" in red
    assert "Stop d'au moins" not in red  # seules les règles enfreintes sont dites
    assert "stop doit être sous" in tool.run("achat", 4280, 4290, "or").text


def test_tool_works_without_market_data(tmp_path):
    tool, _ = make_check_tool(tmp_path, fail_market=True)
    result = tool.run("achat", 4280, 4260, "or", 4320, 1)
    assert "Feu orange : rien d'enfreint, à vérifier : Données de marché" in result.text
    assert "cours indisponibles" in result.display.data["items"][1]["meta"]


def test_a_priced_trade_idea_stays_local_in_trading_mode():
    mode = TradingMode()
    assert mode.route("Je veux acheter l'or à 4 160, stop 4 140") == "local"
    assert mode.route("vente EUR/USD 1,1650 SL 1,1680") == "local"
    assert mode.route("est-ce que ce trade respecte mon plan ?") == "local"
    assert mode.route("fais-moi la check-list") == "local"
    assert mode.route("faut-il acheter l'or en ce moment ?") == "analysis"


def test_rules_editor_saves_the_figures(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.trading_rules import TradingRulesRow

    QApplication.instance() or QApplication([])
    path = tmp_path / "rules.json"
    row = TradingRulesRow(path)
    row.inputs["min_rr"].setValue(3)
    row.inputs["capital"].setValue(8000)
    row.save()
    saved = load_rules(path)
    assert saved.min_rr == 3.0 and saved.capital == 8000 and saved.trend_ema == 200
    assert "enregistrées" in row.status.text()
    row.inputs["rsi_low"].setValue(60)
    row.save()
    assert "zone du RSI" in row.status.text() and load_rules(path).rsi_low == 40
    assert not TradingRulesRow(None).isEnabled()
