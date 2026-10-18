"""La page Trading (menu ☰ → Trading) : vue d'ensemble, journal et réglages du trading."""

from types import SimpleNamespace

import pytest
from fakes import SETTINGS
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from friday.core import env_file
from friday.trading.alerts.store import AlertStore
from friday.trading.journal import TradeJournal
from friday.ui.desktop.trading.overview import alerts_text

app = QApplication.instance() or QApplication([])


@pytest.fixture
def window(tmp_path, monkeypatch):
    from test_desktop import StubAssistant

    from friday.ui.desktop.main_window import MainWindow

    env = tmp_path / ".env"
    env.write_text("TRADING_HOURS=9-18\n", "utf-8")
    monkeypatch.setattr(env_file, "ENV_PATH", env)  # jamais le vrai .env
    assistant = StubAssistant()
    store = AlertStore(tmp_path / "alertes.json")
    trading = SimpleNamespace(journal=TradeJournal(tmp_path / "t.db"),
                              alerts=SimpleNamespace(store=store))  # fmt: skip
    assistant.components = SimpleNamespace(briefing=None, google=None, trading=trading)
    w = MainWindow(SETTINGS, assistant=assistant, preferences_path=tmp_path / "i.json")
    w.resize(1000, 700)
    w.show()
    yield w, trading, env
    w.close()


def test_menu_opens_the_trading_page_and_escape_closes_it(window):
    w, trading, _ = window
    w.show_page_named("Trading")
    QTest.qWait(400)
    page = w.trading_page
    assert w.trading_showing and page.window() is w and page.current_tab == "Vue d'ensemble"
    assert page.overview.curve.isVisibleTo(page)
    trading.journal.open_trade("EURUSD", "achat", 1.10, 1.09)  # noté à la voix
    page.overview.refresh()
    assert "1 en cours" in page.overview.stats.text()
    w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    QTest.qWait(400)
    assert not w.trading_showing and w.trading_page is page  # gardée pour la suite


def test_trading_settings_moved_to_the_page_with_their_own_save_bar(window):
    w, _, env = window
    w.open_settings("Trading")  # « ouvre les réglages du trading »
    QTest.qWait(400)
    tab = w.trading_page.settings
    assert w.trading_showing and w.trading_page.current_tab == "Réglages"
    assert not w.settings_showing
    hours, _ = tab.form._controls["TRADING_HOURS"]
    assert tab.bar.isHidden()
    hours.setText("8-17")
    assert not tab.bar.isHidden() and tab.bar.banner.text() == "1 réglage modifié"
    tab.bar.save_button.click()
    assert "TRADING_HOURS=8-17" in env.read_text("utf-8")
    assert not tab.bar.restart_button.isHidden()
    w.open_settings()
    assert "TRADING_HOURS" not in w.settings_window.changes() | {
        k: v for form in w.settings_window.forms for k, v in form._controls.items()
    }  # plus dans les Réglages de Friday


def test_overview_lists_watched_setups_and_levels(tmp_path):
    store = AlertStore(tmp_path / "alertes.json")
    assert "Aucune alerte" in alerts_text(SimpleNamespace(store=store))
    store.add_setup("XAUUSD")
    store.add_level("EURUSD", 1.12, True)
    text = alerts_text(SimpleNamespace(store=store))
    assert "Setups surveillés (1)" in text and "au-dessus de 1.12" in text
