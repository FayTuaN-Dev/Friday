"""Backtest du plan (T2) : règles rejouées sans voir le futur, bilan en R, variantes, outil."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from friday.tools.backtest import BacktestTool, spread_of
from friday.trading.backtest.engine import Trade, simulate
from friday.trading.backtest.report import Report, r_text, variants
from friday.trading.backtest.series import atr_series, ema_series, rsi_series
from friday.trading.instruments import by_symbol
from friday.trading.market import Candle, MarketUnavailable, atr, ema, rsi
from friday.trading.mode import TradingMode
from friday.trading.plan_rules import PlanRules, save_rules

HOUR_START = datetime(2026, 9, 1, tzinfo=UTC)


def bars(closes, start=HOUR_START, hours=1, wick=5):
    return [Candle(start + timedelta(hours=i * hours), c, c + wick, c - wick, c)
            for i, c in enumerate(closes)]  # fmt: skip


def setup_closes():
    """Hausse puis repli en dents de scie : le plan achète vers la 128e bougie (entrée 4 284,
    stop à 1,5 ATR = 4 269, objectif 2 R = 4 314)."""
    closes = [4100 + 2 * i for i in range(100)]
    for i in range(30):
        closes.append(closes[-1] + (-3 if i % 2 == 0 else 2))
    closes[-1] = closes[-2] + 2.5
    return closes


DAILY = bars([3000 + 4 * i for i in range(300)], datetime(2025, 9, 1, tzinfo=UTC), 24)


def test_series_end_on_the_same_values_as_the_checklist():
    closes = setup_closes()
    candles = bars(closes)
    assert ema_series(closes, 50)[-1] == pytest.approx(ema(closes, 50))
    assert rsi_series(closes)[-1] == pytest.approx(rsi(closes))
    assert atr_series(candles)[-1] == pytest.approx(atr(candles))
    assert ema_series(closes, 50)[48] is None and ema_series([1, 2], 3) == [None, None]


def test_a_winning_setup_is_taken_and_closed_at_the_target():
    closes = setup_closes()
    up = closes + [closes[-1] + 3 * k for k in range(1, 40)]
    (trade,) = simulate(bars(up), DAILY, PlanRules())
    assert (trade.direction, trade.entry, trade.stop, trade.target) == ("achat", 4284, 4269, 4314)
    assert trade.result_r == 2.0
    spread = simulate(bars(up), DAILY, PlanRules(), spread=1.5)[0]
    assert spread.result_r == pytest.approx(2.0 - 0.1)  # 1,5 de spread pour 15 de risque


def test_a_losing_setup_hits_the_stop_and_open_trades_are_left_out():
    closes = setup_closes()
    down = closes + [closes[-1] - 3 * k for k in range(1, 15)]
    assert [t.result_r for t in simulate(bars(down), DAILY, PlanRules())] == [-1.0]
    assert simulate(bars(closes + [closes[-1]] * 3, wick=1), DAILY, PlanRules()) == []


def test_exits_are_prudent_stop_first_and_gaps_at_the_open():
    from friday.trading.backtest.engine import _exit

    def trade():
        return Trade(HOUR_START, "achat", 100, 90, 120)

    both = Candle(HOUR_START, 100, 125, 85, 110)  # stop ET objectif dans la bougie
    t = trade()
    assert _exit(t, both, 0) and t.result_r == -1
    gap = Candle(HOUR_START, 80, 82, 78, 81)  # ouverture sous le stop
    t = trade()
    assert _exit(t, gap, 0) and t.result_r == -2
    t = Trade(HOUR_START, "vente", 100, 110, 80)
    assert _exit(t, Candle(HOUR_START, 95, 96, 79, 82), 0) and t.result_r == 2
    assert not _exit(trade(), Candle(HOUR_START, 100, 105, 95, 101), 0)


def test_the_trend_uses_only_finished_days():
    closes = setup_closes()
    up = closes + [closes[-1] + 3 * k for k in range(1, 40)]
    future = bars([3000 + 4 * i for i in range(300)], HOUR_START, 24)  # pas encore terminées
    assert simulate(bars(up), future, PlanRules()) == []
    assert len(simulate(bars(up), future, PlanRules(trend_ema=0))) >= 1


def test_report_figures():
    report = Report("Ton plan", [Trade(HOUR_START, "achat", 1, 0, 2, result_r=r)
                                 for r in (2, -1, -1, -1, 2, -1)])  # fmt: skip
    assert report.count == 6 and report.win_rate == pytest.approx(100 / 3)
    assert report.expectancy == 0 and report.total == 0
    assert report.worst_streak == 3 and report.drawdown == 3
    assert report.margin == pytest.approx(2 * (2.4 / 6) ** 0.5)  # variance sur n − 1
    assert "6 trades, 33 % gagnants, 0,00 R par trade en moyenne (± 1,26)" in report.line()
    assert r_text(-0.001) == "0,00 R" and r_text(0.354) == "+0,35 R"
    assert Report("Vide", []).line() == "Vide : aucun trade sur la période"


def test_variants_change_one_rule_and_skip_duplicates():
    labels = [label for label, _ in variants(PlanRules())]
    assert labels[0] == "Ton plan" and "Objectif 3 R" in labels and len(labels) == 8
    labels = [label for label, _ in variants(PlanRules(min_rr=3, rsi_turning=False))]
    assert "Objectif 3 R" not in labels and "Sans « RSI qui repart »" not in labels


def test_spread_by_kind():
    assert spread_of(by_symbol("EURUSD"), 1.16) == pytest.approx(0.0001)
    assert spread_of(by_symbol("XAUUSD"), 4100) == pytest.approx(0.3)
    assert spread_of(by_symbol("AAPL"), 200) == pytest.approx(0.1)


def make_tool(tmp_path, closes=None, error=None):
    calls = []

    def history(instrument):
        calls.append(instrument.symbol)
        if error:
            raise MarketUnavailable(error)
        series = closes or setup_closes() + [setup_closes()[-1] + 3 * k for k in range(1, 40)]
        return bars(series), DAILY

    trading = SimpleNamespace(rules_path=tmp_path / "rules.json",
                              instrument_for=lambda q: by_symbol("XAUUSD"))  # fmt: skip
    return BacktestTool(trading, history), calls


def test_tool_reports_the_plan_and_its_variants(tmp_path):
    tool, calls = make_tool(tmp_path)
    result = tool.run("or")
    spoken = "« Sur l'or, du 01/09/2026 au 08/09/2026, en bougies 1 h : 1 trade, 100 % gagnants"
    assert spoken in result.text
    assert "moins de 30 trades, c'est trop peu pour conclure" in result.text
    items = result.display.data["items"]
    assert items[0]["text"] == "Ton plan" and items[-1]["text"] == "Comment c'est calculé"
    tool.run("or", objectif=3)
    assert calls == ["XAUUSD"]  # historique gardé en mémoire
    mine = tool.run("or", objectif=3, stop=1.5).text
    assert "Ta variante (objectif 3 R, stop 1,5 ATR) : 1 trade" in mine.split("EXACTEMENT")[-1]
    save_rules(tmp_path / "rules.json", replace(PlanRules(), trend_ema=0))
    assert "Sans filtre de tendance" not in tool.run("or").text  # règles relues à chaque fois


def test_tool_says_when_history_is_missing(tmp_path):
    tool, _ = make_tool(tmp_path, error="Yahoo en panne.")
    assert "Backtest impossible : Yahoo en panne." in tool.run("or").text
    assert "Instrument inconnu" in tool.run("zzzz-??").text


def test_backtest_requests_stay_local_in_trading_mode():
    mode = TradingMode()
    for text in ("teste mon plan sur l'or", "fais un backtest sur EUR/USD",
                 "mon plan aurait-il gagné sur l'or ?", "et avec un objectif à 3 R ?"):  # fmt: skip
        assert mode.route(text) == "local", text
