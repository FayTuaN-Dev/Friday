"""La page Trading (menu ☰ → Trading) : elle couvre la fenêtre de Friday, sous la barre de
titre, avec ses onglets : « Vue d'ensemble », « Journal » (le journal de trading, qui avait sa
fenêtre à part), « Setups » (le carnet de la surveillance et les avis de Claude) et
« Réglages » (sortis des Réglages de Friday). Échap ou ✕ la referment."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from friday.ui.desktop import theme
from friday.ui.desktop.icons import icon
from friday.ui.desktop.trading.overview import TradingOverview
from friday.ui.desktop.trading.settings_tab import TradingSettings
from friday.ui.desktop.trading.setups_tab import SetupsView

TABS = ("Vue d'ensemble", "Journal", "Setups", "Réglages")


def journal_tab(trading) -> QWidget:
    if trading is None:
        return QLabel("Le trading est désactivé (Réglages → Fonctions).", objectName="Hint")
    from friday.core.config import DATA_DIR
    from friday.ui.desktop.journal.window import JournalView

    snapshot = getattr(trading, "entry_capture", None)  # capture d'entrée, si possible
    return JournalView(trading.journal, snapshot, DATA_DIR / "journal_captures")


class TradingPage(QFrame):
    def __init__(self, main_window) -> None:
        super().__init__(objectName="SettingsCard")
        self.setAttribute(Qt.WA_StyledBackground)
        self.main_window = main_window
        self.components = main_window.assistant.components  # None : Friday se charge encore
        trading = getattr(self.components, "trading", None)
        translate = self._translate_plan if getattr(trading, "translator", None) else None
        overview = QScrollArea(widgetResizable=True)
        overview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.overview = TradingOverview(trading)
        overview.setWidget(self.overview)
        self.journal = journal_tab(trading)
        journal = QScrollArea(widgetResizable=True)  # courbe, tableau et formulaire : ça défile
        journal.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # fenêtre étroite
        journal.setWidget(self.journal)
        self.setups = SetupsView(getattr(getattr(trading, "alerts", None), "setups", None))
        self.settings = TradingSettings(trading, main_window.restart, translate)
        self.stack = QStackedWidget()
        for widget in (overview, journal, self.setups, self.settings):
            self.stack.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(self._header())
        layout.addWidget(self.stack, 1)

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel("TRADING", objectName="SettingsHeader"))
        row.addSpacing(12)
        self.tabs = QButtonGroup(self)
        for index, name in enumerate(TABS):
            button = QPushButton(name, objectName="SettingsSmall", checkable=True)
            button.setFocusPolicy(Qt.NoFocus)
            self.tabs.addButton(button, index)
            row.addWidget(button)
        self.tabs.button(0).setChecked(True)
        self.tabs.idClicked.connect(self._show)
        row.addStretch(1)
        close = QPushButton(objectName="PopupClose", toolTip="Fermer (Échap)")
        close.setIcon(icon("close", theme.current().muted, 14))
        close.setIconSize(QSize(14, 14))
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        row.addWidget(close)
        return row

    def _show(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.overview.refresh()
        elif index == TABS.index("Setups"):
            self.setups.refresh()

    @property
    def current_tab(self) -> str:
        return TABS[self.stack.currentIndex()]

    def show_tab(self, name: str) -> None:
        if name in TABS:
            index = TABS.index(name)
            self.tabs.button(index).setChecked(True)
            self._show(index)

    def _translate_plan(self, name: str) -> None:
        """« Traduire en règles » : comme le dire (plus besoin du mode trading)."""
        self.main_window.assistant.submit_text(f"traduis le plan {name}")

    def close(self) -> bool:
        """La page repart (overlay.py), puis elle est cachée : gardée pour la suite."""
        overlay = self.parent()
        if overlay is not None and hasattr(overlay, "dismiss"):
            overlay.dismiss()
        else:
            self.deleteLater()
        return True
