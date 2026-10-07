"""Formulaire « Nouveau trade » du journal : vérifié avant d'écrire (instrument connu, stop et
objectif du bon côté de l'entrée), pour que les résultats en R soient justes ; avec les notes
qui font apprendre le journal (setup, plan, état d'esprit) et la capture d'entrée."""

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from friday.trading import risk_calc
from friday.trading.instruments import parse_price
from friday.trading.journal import TradeJournal
from friday.trading.journal_export import save_capture
from friday.ui.desktop.journal.notes import TradeNotes

log = logging.getLogger(__name__)


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

    def __init__(self, journal: TradeJournal, snapshot=None, folder: Path | None = None) -> None:
        """`snapshot(symbole)` : PNG du graphique TradingView s'il l'affiche, sinon None."""
        super().__init__(objectName="JournalForm")
        self.journal, self.snapshot, self.folder = journal, snapshot, folder
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
        self.notes = TradeNotes(journal)
        grid.addWidget(self.notes, 3, 0, 1, 3)
        self.with_capture = QCheckBox("Capture du graphique")
        self.with_capture.setToolTip("Gardée sur ce PC, si TradingView affiche l'instrument")
        self.with_capture.setChecked(snapshot is not None)
        self.with_capture.setEnabled(snapshot is not None and folder is not None)
        grid.addWidget(self.with_capture, 3, 3)
        self.message = QLabel(objectName="Hint", wordWrap=True)
        grid.addWidget(self.message, 4, 0, 1, 3)
        grid.addWidget(add, 4, 3)

    def submit(self) -> None:
        try:
            symbol, direction, entry, stop, target, lots = validate(
                self.instrument.text(), self.direction.currentText(), self.entry.text(),
                self.stop.text(), self.target.text(), self.lots.text())  # fmt: skip
        except FormError as error:
            self.message.setText(f"⚠️ {error}")
            return
        reason = self.reason.text().strip()
        trade = self.journal.open_trade(symbol, direction, entry, stop, target, lots, reason,
                                        **self.notes.values())  # fmt: skip
        shot = self._capture(trade.id, symbol)
        for field in (self.entry, self.stop, self.target, self.lots, self.reason):
            field.clear()
        self.notes.clear()
        self.notes.reload()
        self.message.setText(f"Trade n°{trade.id} ajouté.{shot}")
        self.added.emit(trade.id)

    def _capture(self, trade_id: int, symbol: str) -> str:
        if not self.with_capture.isChecked() or self.snapshot is None or self.folder is None:
            return ""
        try:
            image = self.snapshot(symbol)
        except Exception as error:
            log.info("Capture d'entrée impossible : %s", error)
            image = None
        if not image:
            return " (pas de capture : TradingView n'affiche pas cet instrument)"
        self.journal.annotate(trade_id, capture=save_capture(self.folder, trade_id, image))
        return " Capture gardée."
