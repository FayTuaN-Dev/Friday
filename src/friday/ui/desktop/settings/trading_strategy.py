"""Réglages → Trading : « Ma stratégie » — celle que suivent backtest, alertes, check-list et
briefing : un de tes plans écrits (une fois traduit) ou une stratégie de base. Un instrument
peut en avoir une à lui (« choisis le plan Cassure Londres pour l'or »)."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QVBoxLayout

from friday.trading.instruments import by_symbol
from friday.trading.plan_book import PREFIX
from friday.trading.strategies import STRATEGIES
from friday.trading.strategy_choice import DEFAULT


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
        self.box.currentIndexChanged.connect(self._changed)
        layout.addWidget(self.box)
        self.note = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.note)
        self.setEnabled(choice is not None)
        self._seen = None
        if choice is not None:
            self.reload()
            self._watch = QTimer(self, interval=2000)  # un plan ajouté ou traduit à côté
            self._watch.timeout.connect(self.reload)
            self._watch.start()

    def reload(self) -> None:
        plans = self.choice.book.plans()
        seen = [(p["id"], p["nom"], bool(p["spec"])) for p in plans]
        if seen == self._seen:
            return
        self._seen = seen
        self.box.blockSignals(True)
        self.box.clear()
        for plan in plans:
            if plan["spec"]:
                self.box.addItem(f"Ton plan « {plan['nom']} »", PREFIX + plan["id"])
        for strategy in STRATEGIES:
            self.box.addItem(strategy.label[0].upper() + strategy.label[1:], strategy.name)
        current = self.choice.default().name
        self.box.setCurrentIndex(max(0, self.box.findData(current)))
        self.box.blockSignals(False)
        self._explain()

    def _changed(self) -> None:
        self.choice.set(DEFAULT, self.box.currentData())
        self._explain()

    def _explain(self) -> None:
        lines = []
        waiting = [p["nom"] for p in self.choice.book.plans() if not p["spec"]]
        if waiting:
            lines.append("À traduire avant de pouvoir les choisir : "
                         + ", ".join(f"« {n} »" for n in waiting) + ".")  # fmt: skip
        for symbol in (s for s in self.choice.chosen() if s != DEFAULT):
            item = by_symbol(symbol)
            lines.append(f"{item.name if item else symbol} : {self.choice.get(symbol).label} "
                         "(choisie pour cet instrument)")  # fmt: skip
        self.note.setText("\n".join(lines))
