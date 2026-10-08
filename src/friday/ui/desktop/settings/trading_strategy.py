"""Réglages → Trading : « Ma stratégie » — celle que suivent backtest, alertes, check-list et
briefing : ton plan écrit (une fois traduit) ou une stratégie de base. Un instrument peut en
avoir une à lui (« choisis la cassure de range pour l'or »)."""

from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QVBoxLayout

from friday.trading.instruments import by_symbol
from friday.trading.strategies import STRATEGIES
from friday.trading.strategy_choice import DEFAULT, MINE


class StrategyRow(QFrame):
    def __init__(self, choice) -> None:
        super().__init__(objectName="SettingsRow")
        self.choice = choice
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(QLabel("Ma stratégie", objectName="SettingsLabel"))
        layout.addWidget(QLabel(
            "Celle que suivent le backtest, les alertes, la check-list et le briefing. « Compare "
            "les stratégies sur l'or » dit lesquelles ont fonctionné sur l'historique.",
            objectName="Hint", wordWrap=True))  # fmt: skip
        self.box = QComboBox()
        self.box.addItem("Ton plan écrit", MINE)
        for strategy in STRATEGIES:
            self.box.addItem(strategy.label[0].upper() + strategy.label[1:], strategy.name)
        layout.addWidget(self.box)
        self.note = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.note)
        self.setEnabled(choice is not None)
        if choice is not None:
            current = choice.chosen().get(DEFAULT, MINE)
            self.box.setCurrentIndex(max(0, self.box.findData(current)))
            self.box.currentIndexChanged.connect(self._changed)
            self._explain()

    def _changed(self) -> None:
        self.choice.set(DEFAULT, self.box.currentData())
        self._explain()

    def _explain(self) -> None:
        lines = []
        if self.box.currentData() == MINE and self.choice.custom() is None:
            lines.append("⚠️ Ton plan n'est pas encore traduit en règles : en attendant, le "
                         "modèle « repli sur moyenne » est utilisé.")  # fmt: skip
        for symbol in (s for s in self.choice.chosen() if s != DEFAULT):
            item = by_symbol(symbol)
            lines.append(f"{item.name if item else symbol} : {self.choice.get(symbol).label} "
                         "(choisie pour cet instrument)")  # fmt: skip
        self.note.setText("\n".join(lines))
