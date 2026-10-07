"""Journal qui apprend (T4) : setup, plan respecté, état d'esprit, capture d'entrée,
statistiques par catégorie, constats, et revue hebdomadaire anonyme par Claude."""

import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from friday.tools.trading_journal import AnnotateTradeTool, LogTradeTool, TradeStatsTool
from friday.trading import Trading
from friday.trading.context_builder import ContextBuilder
from friday.trading.journal import TradeJournal
from friday.trading.journal_stats import KEYS, breakdown, groups, lessons, review_text, week
from friday.trading.mode import TradingMode

app = QApplication.instance() or QApplication([])


@pytest.fixture
def journal(tmp_path):
    return TradeJournal(tmp_path / "trading.db")


def closed(journal, setup, plan_ok, mood, exit_price, pair="EURUSD", reason=""):
    """Achat à 1,10, stop 1,09 : sortie 1,12 = +2 R, 1,09 = −1 R."""
    trade = journal.open_trade(pair, "achat", 1.10, 1.09, None, 0.37, reason, setup, plan_ok, mood)
    return journal.close_trade(trade.id, exit_price)


def filled(journal):
    for _ in range(3):
        closed(journal, "Repli EMA50", True, "calme", 1.12)
    for _ in range(3):
        closed(journal, "cassure", False, "impatient", 1.09)
    closed(journal, "repli ema50", True, "calme", 1.09)  # même setup, autre casse


def test_an_old_journal_gets_the_new_columns(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, opened_at TEXT NOT NULL, pair TEXT "
               "NOT NULL, direction TEXT NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL, target "
               "REAL, lots REAL, reason TEXT NOT NULL DEFAULT '', capture TEXT, exit REAL, "
               "closed_at TEXT, result_r REAL)")  # fmt: skip
    db.execute("INSERT INTO trades (opened_at, pair, direction, entry, stop) VALUES "
               "('2026-10-01T10:00:00', 'EURUSD', 'achat', 1.1, 1.09)")  # fmt: skip
    db.commit()
    db.close()
    (old,) = TradeJournal(path).all_trades()
    assert (old.setup, old.plan_ok, old.mood, old.capture) == ("", None, "", None)


def test_notes_are_saved_and_completed_later(journal):
    trade = journal.open_trade("XAUUSD", "vente", 4160, 4180, setup=" Cassure ", mood="stressé")
    assert (trade.setup, trade.plan_ok, trade.mood) == ("Cassure", None, "stressé")
    version = journal.version
    trade = journal.annotate(trade.id, plan_ok=False, mood="revanche", lots=99)  # lots ignoré
    assert trade.plan_ok is False and trade.mood == "revanche" and trade.setup == "Cassure"
    assert journal.version > version and journal.annotate(999, mood="calme") is None


def test_groups_and_lessons(journal):
    filled(journal)
    trades = journal.all_trades()
    setups = groups(trades, KEYS["setup"])
    assert [(g.name, g.count) for g in setups] == [("Repli EMA50", 4), ("cassure", 3)]
    assert setups[0].average == pytest.approx(1.25) and setups[1].win_rate == 0
    found = lessons(trades)
    assert "Plan respecté : +1,25 R en moyenne ; plan non respecté : -1,00 R (3 trades)." in found
    assert any("le meilleur est « calme » (+1,25 R), le pire « impatient »" in x for x in found)
    assert "Le setup « cassure » perd en moyenne (-1,00 R sur 3 trades) : à revoir, ou à " \
           "abandonner." in found  # fmt: skip
    assert "Par setup :" in breakdown(trades) and "Par état d'esprit :" in breakdown(trades)
    assert lessons(trades[:2]) == []  # trop peu de trades : aucune leçon


def test_weekly_review_is_anonymous(journal):
    filled(journal)
    old = closed(journal, "vieux setup", True, "calme", 1.12, reason="secret de Valentin")
    journal._db.execute("UPDATE trades SET closed_at = '2026-01-01T10:00:00' WHERE id = ?",
                        (old.id,))  # fmt: skip
    now = datetime.now() + timedelta(minutes=1)
    assert len(week(journal.all_trades(), now)) == 7
    text = review_text(journal.all_trades(), journal.summary(), now)
    assert "Cette semaine : 7 trade(s) clôturé(s)." in text
    assert "achat EURUSD, ouvert" in text and "setup « cassure », plan NON respecté" in text
    assert "Constats calculés sur le PC :" in text
    for private in ("1.1", "1,1", "0.37", "0,37", "secret", "Valentin"):
        assert private not in text  # ni prix, ni taille, ni raison écrite


def test_review_goes_to_claude_without_market_or_chart(journal, tmp_path):
    from test_trading import FakeJob, StubLibrary

    from friday.tools.trading_analysis import TradingAnalysisTool

    filled(journal)
    journal.annotate(1, setup="méthode Valentin")
    builder = ContextBuilder(StubLibrary([]), journal, blocklist=("Valentin",))
    asked = []
    tool = TradingAnalysisTool(builder, FakeJob(tmp_path), journal, lambda *a: None,
                               lambda q: asked.append(q), lambda i: True)  # fmt: skip
    tool.confirmation({"question": "fais ma revue de la semaine"})
    packet = tool.preview({})
    (item,) = [i for i in packet.items if i.kind == "bilan"]
    assert "Statistiques de tout le journal" in item.text and "Valentin" not in item.text
    assert asked == [] and packet.images == []  # ni instrument, ni capture
    mode = TradingMode()
    assert mode.route("fais ma revue de la semaine") == "analysis"
    assert mode.route("revue de mon journal") == "analysis"  # « journal » ne la garde pas locale


def test_log_trade_keeps_a_capture_and_asks_for_missing_notes(journal, tmp_path):
    folder = tmp_path / "captures"
    tool = LogTradeTool(journal, lambda symbol: b"\x89PNG" if symbol == "XAUUSD" else None, folder)
    text = tool.run("or", "vente", 4160, 4180, setup="cassure").text
    trade = journal.get(1)
    assert "Capture du graphique gardée" in text and trade.capture.endswith("trade-1.png")
    assert (folder / "trade-1.png").read_bytes() == b"\x89PNG"
    assert "si le plan est respecté, ton état d'esprit" in text and "le setup" not in text
    tool.run("EUR/USD", "achat", 1.1, 1.09, plan_respected=True, setup="x", mood="calme")
    assert journal.get(2).capture is None  # TradingView n'affiche pas l'EUR/USD

    def broken(symbol):
        raise RuntimeError("fenêtre introuvable")

    assert "noté" in LogTradeTool(journal, broken, folder).run("or", "achat", 1, 0.9).text


def test_annotate_and_stats_tools(journal):
    filled(journal)
    assert "complété" in AnnotateTradeTool(journal).run(1, mood="fatigué").text
    assert "Pas de trade n°99" in AnnotateTradeTool(journal).run(99, mood="calme").text
    text = TradeStatsTool(journal).run().text
    assert text.startswith("Dis EXACTEMENT : « 7 trades clôturés") and "Plan respecté" in text


def test_entry_capture_only_when_the_chart_shows_the_instrument(journal):
    capture = SimpleNamespace(window_title=lambda: "XAUUSD 4 130,0 ▲", capture=lambda: b"png")
    trading = Trading(TradingMode(), journal, None, None, capture=capture)
    assert trading.entry_capture("XAUUSD") == b"png"
    assert trading.entry_capture("EURUSD") is None


def test_window_notes_completion_capture_and_insights(journal, tmp_path):
    from friday.ui.desktop.journal.window import COLUMNS, JournalWindow

    filled(journal)
    window = JournalWindow(journal, lambda symbol: b"\x89PNG", tmp_path / "captures")
    assert "Plan respecté" in window.insights.lessons.text()
    assert "Par setup" in window.insights.detail.toPlainText()
    assert window.table.horizontalHeaderItem(COLUMNS.index("Setup")).text() == "Setup"
    form = window.form
    form.instrument.setText("or")
    form.entry.setText("4160")
    form.stop.setText("4180")
    form.direction.setCurrentText("vente")
    form.notes.setup.setEditText("cassure")
    form.notes.plan.setCurrentText("oui")
    form.notes.mood.setEditText("calme")
    form.submit()
    trade = journal.get(8)
    assert (trade.setup, trade.plan_ok, trade.mood) == ("cassure", True, "calme")
    assert trade.capture and "Capture gardée" in form.message.text()
    window.table.selectRow(0)  # le plus récent : n°8
    assert window.capture_button.isEnabled()
    window.notes.mood.setEditText("stressé")
    window.annotate_selected()
    assert journal.get(8).mood == "stressé" and "complété" in window.message.text()
    window.close()


def test_notes_start_empty_so_nothing_is_recorded_by_default(journal):
    from friday.ui.desktop.journal.notes import TradeNotes

    notes = TradeNotes(journal)
    assert notes.values() == {"setup": "", "plan_ok": None, "mood": ""}
    assert "repli EMA50 (plan)" in [notes.setup.itemText(i) for i in range(notes.setup.count())]
