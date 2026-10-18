"""Page Trading → « Vue d'ensemble » : d'un coup d'œil, le bilan du journal et sa courbe en
R, la stratégie suivie (et celles propres à un marché), les alertes en place. Relue toutes
les 2 s tant qu'elle est affichée (un trade noté ou une alerte posée à la voix)."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from friday.trading.instruments import by_symbol
from friday.trading.strategy_choice import DEFAULT
from friday.ui.desktop.journal.equity_chart import EquityChart
from friday.ui.desktop.journal.window import stats_text

SAYINGS = ("« surveille tous les marchés » · « compare les stratégies sur l'or » · "
           "« note ce trade » · « mets une alerte sur l'or à 4200 »")  # fmt: skip


def _name(symbol: str) -> str:
    instrument = by_symbol(symbol)
    return instrument.name if instrument else symbol


def strategy_text(choice) -> str:
    if choice is None:
        return "Aucune stratégie (le trading est désactivé)."
    text = f"Pour tous les marchés : {choice.default().label or choice.default().name}"
    own = [(s, n) for s, n in choice.chosen().items() if s != DEFAULT]
    for symbol, _ in sorted(own):
        strategy = choice.get(symbol)
        text += f"\n{_name(symbol)} : {strategy.label or strategy.name}"
    return text


def alerts_text(alerts) -> str:
    store = getattr(alerts, "store", None)
    found = store.all() if store is not None else []
    if not found:
        return "Aucune alerte. « Surveille l'or » ou « surveille tous les marchés » en pose."
    setups = sorted(_name(a.symbol) for a in found if a.kind == "setup")
    levels = [f"{_name(a.symbol)} {'au-dessus de' if a.above else 'sous'} {a.level:g}"
              for a in found if a.kind == "niveau"]  # fmt: skip
    lines = []
    if setups:
        lines.append(f"Setups surveillés ({len(setups)}) : {', '.join(setups)}")
    if levels:
        lines.append("Niveaux : " + " · ".join(levels))
    return "\n".join(lines)


def _card(title: str, *widgets: QWidget) -> QFrame:
    card = QFrame(objectName="SettingsRow")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 10, 14, 12)
    layout.addWidget(QLabel(title, objectName="SettingsLabel"))
    for widget in widgets:
        layout.addWidget(widget)
    return card


class TradingOverview(QWidget):
    def __init__(self, trading) -> None:
        super().__init__(objectName="SettingsPage")
        self.trading = trading
        self.stats = QLabel(objectName="SettingsTitle", wordWrap=True)
        self.curve = EquityChart()
        self.strategy = QLabel(objectName="Hint", wordWrap=True)
        self.alerts = QLabel(objectName="Hint", wordWrap=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(12)
        layout.addWidget(_card("Mon journal", self.stats, self.curve))
        layout.addWidget(_card("Ma stratégie", self.strategy))
        layout.addWidget(_card("Mes alertes", self.alerts))
        layout.addWidget(QLabel(f"À dire à Friday : {SAYINGS}", objectName="Hint",
                                wordWrap=True))  # fmt: skip
        layout.addStretch()
        self._seen = None  # version du journal affichée
        self._watch = QTimer(self, interval=2000)
        self._watch.timeout.connect(self._follow)
        self._watch.start()
        self.refresh()

    def _follow(self) -> None:
        if self.isVisible():
            self.refresh()

    def refresh(self) -> None:
        journal = getattr(self.trading, "journal", None)
        if journal is None:
            self.stats.setText("Le trading est désactivé (Réglages → Fonctions).")
        else:
            self.stats.setText(stats_text(journal))
            if journal.version != self._seen:  # la courbe garde son survol sinon
                self._seen = journal.version
                self.curve.set_points(journal.equity())
        self.curve.setVisible(journal is not None)
        self.strategy.setText(strategy_text(getattr(self.trading, "choice", None)))
        self.alerts.setText(alerts_text(getattr(self.trading, "alerts", None)))
