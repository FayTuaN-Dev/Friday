"""Formulaire « Nouveau trade » du journal : vérifié avant d'écrire (instrument connu, stop et
objectif du bon côté de l'entrée), pour que les résultats en R soient justes."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QLabel, QLineEdit, QPushButton

from friday.trading import risk_calc
from friday.trading.instruments import parse_price
from friday.trading.journal import TradeJournal


class FormError(ValueError):
    """Message pour l'utilisateur."""


def number(text: str, name: str, required: bool = True) -> float | None:
    if not text.strip():
        if required:
            raise FormError(f"Il manque {name}.")
        return None
    value = parse_price(text)
    if value is None or value <= 0:
        raise FormError(f"{name.capitalize()} : nombre invalide (« {text} »).")
    return value


def validate(instrument: str, direction: str, entry: str, stop: str, target: str, lots: str):
    """(symbole, sens, entrée, stop, objectif, lots), ou FormError."""
    try:
        symbol = risk_calc.resolve(instrument).symbol
    except ValueError as error:
        raise FormError(str(error)) from error
    entry_v = number(entry, "le prix d'entrée")
    stop_v = number(stop, "le stop")
    target_v = number(target, "l'objectif", required=False)
    lots_v = number(lots, "la taille", required=False)
    buying = direction == "achat"
    if (stop_v >= entry_v) if buying else (stop_v <= entry_v):
        side = "sous" if buying else "au-dessus de"
        raise FormError(f"Pour {'un achat' if buying else 'une vente'}, le stop doit être {side} "
                        "l'entrée.")  # fmt: skip
    if target_v is not None and ((target_v <= entry_v) if buying else (target_v >= entry_v)):
        raise FormError("L'objectif doit être du côté du gain, de l'autre côté de l'entrée.")
    return symbol, direction, entry_v, stop_v, target_v, lots_v


class TradeForm(QFrame):
    added = Signal(int)  # numéro du trade

    def __init__(self, journal: TradeJournal) -> None:
        super().__init__(objectName="JournalForm")
        self.journal = journal
        grid = QGridLayout(self)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.addWidget(QLabel("Nouveau trade", objectName="SettingsLabel"), 0, 0, 1, 4)
        self.instrument = QLineEdit(placeholderText="Instrument : EUR/USD, or, AAPL…")
        self.direction = QComboBox()
        self.direction.addItems(["achat", "vente"])
        self.entry = QLineEdit(placeholderText="Entrée")
        self.stop = QLineEdit(placeholderText="Stop")
        self.target = QLineEdit(placeholderText="Objectif (facultatif)")
        self.lots = QLineEdit(placeholderText="Lots (facultatif)")
        self.reason = QLineEdit(placeholderText="Raison : pourquoi ce trade ? (setup, signal…)")
        add = QPushButton("Ajouter", objectName="SettingsPrimary")
        add.clicked.connect(self.submit)
        for column, widget in enumerate((self.instrument, self.direction, self.entry, self.stop)):
            grid.addWidget(widget, 1, column)
        grid.addWidget(self.target, 2, 0)
        grid.addWidget(self.lots, 2, 1)
        grid.addWidget(self.reason, 2, 2, 1, 2)
        self.message = QLabel(objectName="Hint", wordWrap=True)
        grid.addWidget(self.message, 3, 0, 1, 3)
        grid.addWidget(add, 3, 3)

    def submit(self) -> None:
        try:
            symbol, direction, entry, stop, target, lots = validate(
                self.instrument.text(), self.direction.currentText(), self.entry.text(),
                self.stop.text(), self.target.text(), self.lots.text())  # fmt: skip
        except FormError as error:
            self.message.setText(f"⚠️ {error}")
            return
        trade = self.journal.open_trade(symbol, direction, entry, stop, target, lots,
                                        self.reason.text().strip())  # fmt: skip
        for field in (self.entry, self.stop, self.target, self.lots, self.reason):
            field.clear()
        self.message.setText(f"Trade n°{trade.id} ajouté.")
        self.added.emit(trade.id)
