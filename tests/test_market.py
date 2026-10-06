"""Données de marché (PR C) : instruments, indicateurs déterministes, Yahoo, cours BCE."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from friday.trading import Trading
from friday.trading.context_builder import ContextBuilder
from friday.trading.instruments import by_symbol, detect, from_chart_title
from friday.trading.market import (
    Candle,
    MarketUnavailable,
    Quote,
    Snapshot,
    atr,
    fetch,
    pivots,
    regroup,
    rsi,
    sma,
)


def test_instruments_are_detected_from_speech_symbols_and_chart_titles():
    assert detect("et sur l'or ?").symbol == "XAUUSD"
    assert detect("que penses-tu de l'orage") is None
    assert detect("le cours de l'argent").symbol == "XAGUSD"
    assert detect("j'ai de l'argent") is None
    assert detect("regarde l'EUR/USD").symbol == "EURUSD"
    assert detect("gbpjpy en 4h").symbol == "GBPJPY"
    assert detect("analyse l'action AAPL").symbol == "AAPL"
    assert detect("le RSI est haut") is None  # pas une action
    assert from_chart_title("XAUUSD 4 192,7 ▲ +0.4% - Google Chrome").yahoo == "GC=F"
    assert from_chart_title("OANDA:XAGUSD 61,7 ▲").contract == 5000
    assert by_symbol("USDJPY").pip == 0.01 and by_symbol("EURUSD").pip == 0.0001
    assert by_symbol("MC.PA").quote == "EUR" and by_symbol("AAPL").quote == "USD"
    assert by_symbol("or").symbol == "XAUUSD"


def candles(closes, start=datetime(2026, 10, 1, tzinfo=UTC), hours=1):
    return [Candle(start + timedelta(hours=i * hours), c, c + 1, c - 1, c)
            for i, c in enumerate(closes)]  # fmt: skip


def test_indicators_are_computed_locally():
    assert sma([1, 2, 3, 4], 2) == 3.5 and sma([1], 5) is None
    assert rsi(list(range(1, 30))) == 100.0  # que des hausses
    assert rsi([10, 11] * 10) == pytest.approx(50, abs=5)
    assert atr(candles([10] * 20)) == pytest.approx(2)  # bougies de 2 points d'amplitude
    levels = pivots(Candle(datetime.now(UTC), 0, 110, 90, 100))
    assert levels["P"] == 100 and levels["R1"] == 110 and levels["S1"] == 90
    four = regroup(candles(list(range(8))), 4)
    assert len(four) == 2 and four[0].open == 0 and four[0].close == 3 and four[0].high == 4


def yahoo(closes, price=1.1, currency="USD"):
    start = int(datetime(2026, 10, 1, tzinfo=UTC).timestamp())
    payload = {"chart": {"result": [{
        "meta": {"regularMarketPrice": price, "currency": currency,
                 "regularMarketTime": start + 3600, "chartPreviousClose": 1.0},
        "timestamp": [start + i * 3600 for i in range(len(closes))],
        "indicators": {"quote": [{"open": closes, "high": closes, "low": closes,
                                  "close": closes}]},
    }]}}  # fmt: skip

    def get(url, params=None, headers=None, timeout=None):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    return get


def test_yahoo_answers_are_parsed_and_failures_reported():
    quote, bars = fetch("EURUSD=X", "1h", "1mo", yahoo([1.1, None, 1.2]))
    assert quote.price == 1.1 and len(bars) == 2  # bougie incomplète ignorée

    def broken(*args, **kwargs):
        import httpx

        raise httpx.ConnectError("hors ligne")

    with pytest.raises(MarketUnavailable):
        fetch("EURUSD=X", "1h", "1mo", broken)


def test_snapshot_text_is_compact_and_complete():
    instrument = by_symbol("EURUSD")
    hourly = candles([1.10 + i * 0.0001 for i in range(200)])
    daily = candles([1.10 + i * 0.001 for i in range(250)], hours=24)
    snap = Snapshot(instrument, Quote(1.1234, 1.12, "USD", datetime.now(UTC)), hourly, daily)
    text = snap.text()
    for part in ("EUR/USD", "MM200", "RSI14", "ATR14", "Pivots du jour", "Dernières bougies 4 h"):
        assert part in text, part
    assert len(text) < 2000


def test_market_block_joins_the_packet_or_says_why_not():
    instrument = by_symbol("XAUUSD")
    builder = ContextBuilder(market=lambda i: SimpleNamespace(text=lambda: f"Cours de {i.name}"))
    packet = builder.build("Que penses-tu de l'or ?", instrument=instrument)
    assert packet.items[0].kind == "marche" and "Cours de l'or" in packet.render()

    def down(i):
        raise MarketUnavailable("Cours de GC=F indisponibles.")

    packet = ContextBuilder(market=down).build("Et l'or ?", instrument=instrument)
    assert not packet.items and "Analyse sans données de marché" in packet.notes[0]


def test_current_instrument_follows_the_question_then_the_chart(tmp_path):
    chart = SimpleNamespace(window_title=lambda: "GBPJPY 209,85 ▲ +0.5% - Google Chrome")
    trading = Trading(None, None, None, None, capture=chart)
    assert trading.instrument_for("Que penses-tu de ce double sommet ?").symbol == "GBPJPY"
    assert trading.instrument_for("Et sur l'or ?").symbol == "XAUUSD"
    trading.capture = None
    assert trading.instrument_for("Et maintenant ?").symbol == "XAUUSD"  # le dernier utilisé


def test_quote_tool_reads_the_source(monkeypatch):
    from friday.tools import markets

    day = datetime(2026, 10, 6, tzinfo=UTC)
    bars = [Candle(day, 0, 0, 0, 4157.0), Candle(day, 0, 0, 0, 4192.7)]
    monkeypatch.setattr(markets, "fetch", lambda ticker, interval, period: (
        Quote(4192.7, None, "USD", day), bars))  # fmt: skip
    monkeypatch.setattr(markets, "reference_rate", lambda base, quote: (1.1269, "2026-10-06"))
    gold = markets.MarketQuoteTool().run("or").text
    assert "l'or (XAUUSD) : 4192.7 USD (+0.86 % depuis hier)" in gold and "contrat à terme" in gold
    assert "Cours de référence BCE du 2026-10-06 : 1.1269" in markets.MarketQuoteTool().run(
        "EUR/USD").text  # fmt: skip
    assert "inconnu" in markets.MarketQuoteTool().run("???").text
