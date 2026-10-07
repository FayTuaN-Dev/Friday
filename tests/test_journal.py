"""Journal de trading : bilan, suppression, export, et sa fenêtre (formulaire, clôture…)."""

import csv

import pytest
from PySide6.QtWidgets import QApplication

from friday.trading.journal import TradeJournal
from friday.ui.desktop.journal.trade_form import FormError, TradeForm, validate
from friday.ui.desktop.journal.window import JournalWindow, planned_ratio, stats_text

app = QApplication.instance() or QApplication([])


@pytest.fixture
def journal(tmp_path):
    return TradeJournal(tmp_path / "trading.db")  # jamais le vrai journal


def test_stats_delete_and_version(journal):
    assert journal.stats().closed == 0 and journal.stats().win_rate is None
    start = journal.version
    win = journal.open_trade("EURUSD", "achat", 1.1000, 1.0980, 1.1060)
    loss = journal.open_trade("XAUUSD", "vente", 4160, 4180)
    journal.open_trade("GBPUSD", "achat", 1.30, 1.29)  # en cours
    journal.close_trade(win.id, 1.1040)  # +2 R
    journal.close_trade(loss.id, 4180)  # -1 R
    s = journal.stats()
    assert (s.closed, s.open, s.wins) == (2, 1, 1) and s.win_rate == 0.5
    assert s.average_r == pytest.approx(0.5) and s.total_r == pytest.approx(1.0)
    assert journal.version > start  # l'écran sait qu'il doit se rafraîchir
    assert journal.delete_trade(loss.id) and not journal.delete_trade(999)
    assert [t.pair for t in journal.all_trades()] == ["GBPUSD", "EURUSD"]  # récents d'abord


def test_csv_export_for_excel(journal, tmp_path):
    trade = journal.open_trade("EURUSD", "achat", 1.1, 1.098, None, 0.5, "repli MM50")
    journal.close_trade(trade.id, 1.104)
    path = tmp_path / "journal.csv"
    assert journal.export_csv(path) == 1
    rows = list(csv.reader(path.open(encoding="utf-8-sig"), delimiter=";"))
    assert rows[0][2] == "instrument" and rows[1][2] == "EURUSD" and rows[1][-1] == "2.0"


def test_form_checks_before_writing():
    assert validate("or", "vente", "4 160,5", "4180", "4100", "")[:4] == (
        "XAUUSD", "vente", 4160.5, 4180.0)  # fmt: skip
    for args, message in (
        (("???", "achat", "1.1", "1.09", "", ""), "inconnu"),
        (("EUR/USD", "achat", "1.1", "1.12", "", ""), "stop doit être sous"),
        (("EUR/USD", "vente", "1.1", "1.09", "", ""), "au-dessus"),
        (("EUR/USD", "achat", "1.1", "1.09", "1.05", ""), "côté du gain"),
        (("EUR/USD", "achat", "", "1.09", "", ""), "prix d'entrée"),
        (("EUR/USD", "achat", "abc", "1.09", "", ""), "invalide"),
    ):
        with pytest.raises(FormError, match=message):
            validate(*args)


def test_form_adds_a_trade(journal):
    form = TradeForm(journal)
    form.instrument.setText("EUR/USD")
    form.entry.setText("1,1250")
    form.stop.setText("1,1230")
    form.target.setText("1,1290")
    form.reason.setText("repli sur la MM50")
    added = []
    form.added.connect(added.append)
    form.submit()
    trade = journal.get(added[0])
    assert (trade.pair, trade.entry, trade.reason) == ("EURUSD", 1.125, "repli sur la MM50")
    assert form.entry.text() == "" and "ajouté" in form.message.text()
    form.submit()  # entrée vide : refusé, rien d'écrit
    assert "Il manque" in form.message.text() and len(journal.all_trades()) == 1


def test_window_shows_stats_closes_and_deletes(journal):
    trade = journal.open_trade("EURUSD", "achat", 1.1000, 1.0980, 1.1060, reason="cassure")
    window = JournalWindow(journal)
    assert window.table.rowCount() == 1 and "Aucun trade clôturé" in window.stats.text()
    assert window.table.item(0, 7).text() == planned_ratio(trade) == "1 : 3.0"
    window.table.selectRow(0)
    window.exit_price.setText("1,1040")
    window.close_selected()
    assert journal.get(trade.id).result_r == pytest.approx(2.0)
    assert window.table.item(0, 9).text() == "+2.00 R" and "100% gagnants" in window.stats.text()
    assert "total +2,00 R" in window.stats.text() and window.curve.points[-1][3] == 2.0
    window.table.selectRow(0)
    window.delete_selected()  # premier clic : on demande
    assert journal.get(trade.id) is not None and window.delete_button.text() == "Confirmer ?"
    window.delete_selected()
    assert journal.all_trades() == [] and window.table.rowCount() == 0
    window.close()


def test_window_follows_trades_noted_by_voice(journal):
    window = JournalWindow(journal)
    journal.open_trade("XAUUSD", "vente", 4160, 4180)  # comme l'outil log_trade
    window._follow()
    assert window.table.rowCount() == 1 and "1 en cours" in window.stats.text()
    assert "Aucun trade" in stats_text(TradeJournal(":memory:"))
    window.close()


def test_open_journal_by_voice_and_from_settings(tmp_path):
    from types import SimpleNamespace

    from fakes import SETTINGS
    from test_desktop import StubAssistant

    from friday.tools.trading import OpenJournalTool
    from friday.ui.desktop.main_window import MainWindow

    assistant = StubAssistant()
    trading = SimpleNamespace(journal=TradeJournal(tmp_path / "t.db"))
    assistant.components = SimpleNamespace(briefing=None, google=None, trading=trading)
    w = MainWindow(SETTINGS, assistant=assistant, preferences_path=tmp_path / "i.json")
    w.bridge.on_display(OpenJournalTool().run().display)
    app.processEvents()
    assert w.journal_window is not None and w.popups.popups == []
    w.close()


def test_equity_follows_closing_order(journal):
    first = journal.open_trade("EURUSD", "achat", 1.10, 1.09)
    second = journal.open_trade("XAUUSD", "vente", 4160, 4180)
    journal.open_trade("GBPUSD", "achat", 1.30, 1.29)  # en cours : pas sur la courbe
    journal.close_trade(second.id, 4180)  # -1 R, clôturé en premier
    journal.close_trade(first.id, 1.12)  # +2 R
    journal._db.execute(
        "UPDATE trades SET closed_at = '2026-10-07T10:00' WHERE id = ?", (second.id,)
    )
    journal._db.execute(
        "UPDATE trades SET closed_at = '2026-10-07T11:00' WHERE id = ?", (first.id,)
    )
    assert [(n, round(total, 2)) for n, _, _, total in journal.equity()] == [(2, -1.0), (1, 1.0)]


def test_curve_ticks_hover_and_empty_state():
    from types import SimpleNamespace

    from PySide6.QtCore import QPointF

    from friday.ui.desktop.journal.equity_chart import EquityChart, nice_ticks

    assert nice_ticks(-1, 4.75) == [-2, 0, 2, 4, 6]  # ronds, zéro compris, couvre le plus haut
    for low, high in ((-3.2, 0.4), (0, 0.9), (-0.5, 12.3), (0, 57)):
        ticks = nice_ticks(low, high)
        assert ticks[0] <= min(low, 0) and ticks[-1] >= high and 0 in ticks
    assert nice_ticks(0, 0)[0] == 0
    chart = EquityChart()
    chart.resize(600, 200)
    chart.grab()  # sans trade : un message, pas de courbe vide
    chart.set_points([(1, "EURUSD", 1.75, 1.75), (2, "XAUUSD", -1.0, 0.75)])
    shown = []
    import friday.ui.desktop.journal.equity_chart as module

    module.QToolTip.showText = lambda pos, text, widget=None: shown.append(text)
    event = SimpleNamespace(position=lambda: QPointF(590, 50),
                            globalPosition=lambda: QPointF(0, 0))  # fmt: skip
    chart.mouseMoveEvent(event)
    assert chart._hover == 2 and shown == ["Trade n°2 · XAUUSD · -1,00 R · cumul +0,75 R"]
    assert not chart.grab().isNull()
