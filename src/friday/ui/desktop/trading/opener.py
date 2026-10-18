"""La fenêtre principale ouvre ses pages par le menu ☰ de la barre de titre : « Conversation »
(retour à Friday) et « Trading ». La page est construite une fois, au repos après le
démarrage (comme les réglages : la construire au clic figeait Friday), puis gardée."""

from PySide6.QtCore import QPoint

from friday.ui.desktop import theme
from friday.ui.desktop.icons import icon
from friday.ui.desktop.widgets.menus import glass_menu

PAGES = (("Conversation", "send"), ("Trading", "trending"))


class TradingPageMixin:
    trading_page = None
    _trading_overlay = None

    def open_menu(self) -> None:
        accent = theme.current().accent
        menu = glass_menu(self, "Pages")
        for name, symbol in PAGES:
            action = menu.addAction(icon(symbol, accent, 16), name)
            action.setCheckable(True)
            action.setChecked((name == "Trading") == self.trading_showing)
        button = self.title_bar.menu_button
        chosen = menu.exec(button.mapToGlobal(QPoint(0, button.height() + 4)))
        if chosen is not None:
            self.show_page_named(chosen.text())

    def show_page_named(self, name: str) -> None:
        if name == "Trading":
            self.open_trading()
        elif self.trading_showing:
            self.trading_page.close()

    def prepare_trading(self) -> None:
        """Construite une fois Friday chargée ; refaite si elle l'avait été avant (S2)."""
        from friday.ui.desktop.settings.overlay import PageOverlay
        from friday.ui.desktop.trading.page import TradingPage

        page = self.trading_page
        if (page is not None and page.components is not self.assistant.components
                and not self.trading_showing):  # fmt: skip
            self._trading_overlay.deleteLater()  # la page avec lui
            self.trading_page = None
        if self.trading_page is None:
            self.trading_page = TradingPage(self)
            self._trading_overlay = PageOverlay(self.shell, self.trading_page)

    def open_trading(self, tab: str = "") -> None:
        self.prepare_trading()
        if self.settings_showing:
            self.settings_window.close()
        if tab:
            self.trading_page.show_tab(tab)
        self._trading_overlay.open(self._settings_area())

    def open_journal(self) -> None:
        """« Ouvre mon journal » : la page Trading, sur son journal."""
        self.open_trading("Journal")

    @property
    def trading_showing(self) -> bool:
        overlay = self._trading_overlay
        return self.trading_page is not None and overlay is not None and overlay.showing
