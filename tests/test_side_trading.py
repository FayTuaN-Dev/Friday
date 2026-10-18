"""La carte « Trading » des colonnes de côté (W3) : cours, annonce, dernier setup, semaine."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from friday.app.trading_glance import Glance, TradingGlance, next_events
from friday.trading.alerts.setup_log import SetupLog
from friday.trading.calendar import Event
from friday.trading.instruments import by_symbol
from friday.trading.journal import TradeJournal
from friday.trading.market import Quote
from friday.ui.desktop.side.trading_card import TradingCard

app = QApplication.instance() or QApplication([])
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
GOLD, EURUSD = by_symbol("XAUUSD"), by_symbol("EURUSD")


def event(hours, currency="USD", impact="High", title="Non-Farm Payrolls"):
    return Event(NOW + timedelta(hours=hours), currency, title, impact, "", "")


def test_next_events_keep_future_high_impact_of_followed_currencies():
    events = [event(-1), event(3, impact="Medium"), event(5, "JPY"), event(2, title="CPI"),
              event(26, "All", title="G20")]  # fmt: skip
    found = next_events(events, {"USD", "EUR"}, NOW)
    assert [e.title for e in found] == ["CPI", "G20"]


def test_glance_reads_quotes_and_survives_a_dead_calendar():
    from friday.trading.calendar import SourceUnavailable

    def dead():
        raise SourceUnavailable("panne")

    quote = Quote(4163.2, 4145.8, "USD", NOW)
    glance = TradingGlance(lambda: [GOLD, EURUSD], quote=lambda i: quote if i is GOLD else None,
                           events=dead, now=lambda: NOW).read()  # fmt: skip
    assert glance.quotes == [(GOLD, quote), (EURUSD, None)] and glance.events == []


def test_card_shows_prices_news_last_setup_and_week(tmp_path):
    opened = []
    card = TradingCard(opened.append)
    quote = Quote(4163.2, 4145.8, "USD", NOW)
    card.show_glance(Glance([(GOLD, quote), (EURUSD, None)], [event(0.25)]), NOW)
    name, price, change = card.rows[0]
    assert name.text() == "l'or" and price.text() == "4 163,20" and change.text() == "▲ +0,42 %"
    assert card.rows[1][1].text() == "—"
    assert card.news[1].text() == "Non-Farm Payrolls (USD) · dans 15 min"
    assert "e5636b" in card.news[1].styleSheet()  # dans moins de 30 min : en rouge
    path = tmp_path / "setups.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "symbol": "XAGUSD",
                    "side": "vente",
                    "seen": "2026-10-18T13:59:00",
                    "result_r": None,
                }
            ]
        ),
        "utf-8",
    )
    journal = TradeJournal(tmp_path / "j.db")
    trade = journal.open_trade("EURUSD", "achat", 1.10, 1.09)
    journal.close_trade(trade.id, 1.12)
    card.show_local(SetupLog(path), journal, datetime.now())
    assert card.setup[1].text().startswith("L'argent (métal) · vente · il y a ")
    assert card.setup[1].text().endswith("· en cours")
    assert card.week[1].text() == "+2,00 R sur 1 trade(s), 7 jours"
    card.show_glance(Glance(), NOW)
    assert card.markets_note.isVisibleTo(card) and "Aucune annonce" in card.news[1].text()


def test_panels_show_the_card_once_trading_is_loaded():
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget
    from test_side_widgets import FakeSampler

    from friday.app import trading_glance
    from friday.ui.desktop.side.columns import SidePanels

    playing, limits = QFrame(), QFrame()
    playing.has_track = False
    side = SidePanels(playing, limits, {}, FakeSampler())
    window = QWidget()
    row = QHBoxLayout(window)
    row.addWidget(side.left)
    row.addWidget(side.right)
    window.show()
    side.place(True)
    assert not side.cards["trading"].isVisible()  # Friday pas encore chargée
    glance = FakeSampler()
    trading = SimpleNamespace(briefing=SimpleNamespace(instruments=lambda: [GOLD]),
                              alerts=None, journal=None)  # fmt: skip
    original = trading_glance.from_trading
    trading_glance.from_trading = lambda t: TradingGlance(t.briefing.instruments)
    try:
        side.set_trading(trading, glance)
    finally:
        trading_glance.from_trading = original
    assert side.cards["trading"].isVisible() and glance.requests == 1
    assert side.cards["trading"].setup[1].text() == "Aucun setup noté."
    window.close()
