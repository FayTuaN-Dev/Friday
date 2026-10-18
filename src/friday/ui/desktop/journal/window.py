"""Le journal de trading (onglet « Journal » de la page Trading) : le bilan en R, ce que dit
le journal (constats), tous les trades, et les actions (nouveau, compléter setup / plan /
état d'esprit, voir la capture, clôturer au prix de sortie, supprimer en deux clics, exporter
en CSV). Tout reste sur le PC.
Elle se met à jour seule quand le journal change (par exemple un trade noté à la voix)."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from friday.trading.instruments import parse_price
from friday.trading.journal import Trade, TradeJournal
from friday.ui.desktop.journal.equity_chart import EquityChart, fr
from friday.ui.desktop.journal.insights import Insights
from friday.ui.desktop.journal.notes import TradeNotes
from friday.ui.desktop.journal.trade_form import TradeForm

COLUMNS = ("N°", "Ouvert le", "Instrument", "Sens", "Entrée", "Stop", "Objectif", "R/R prévu",
           "Sortie", "Résultat", "Setup", "Plan", "Esprit", "📷", "Raison")  # fmt: skip
RESULT = COLUMNS.index("Résultat")
GAIN, LOSS = QColor("#4cc38a"), QColor("#e5636b")


def planned_ratio(trade: Trade) -> str:
    if trade.target is None or trade.entry == trade.stop:
        return ""
    return f"1 : {abs(trade.target - trade.entry) / abs(trade.entry - trade.stop):.1f}"


def stats_text(journal: TradeJournal) -> str:
    s = journal.stats()
    if not s.closed:
        return f"Aucun trade clôturé pour l'instant · {s.open} en cours"
    return (
        f"{s.closed} trade(s) clôturé(s) · {s.win_rate:.0%} gagnants · moyenne "
        f"{fr(s.average_r, True)} R · total {fr(s.total_r, True)} R · {s.open} en cours"
    )


class JournalView(QWidget):
    def __init__(self, journal: TradeJournal, snapshot=None, folder: Path | None = None) -> None:
        """`snapshot`, `folder` : capture d'entrée (voir TradeForm)."""
        super().__init__()
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.journal = journal
        self.stats = QLabel(objectName="SettingsTitle", wordWrap=True)
        self.body.addWidget(self.stats)
        self.curve = EquityChart()  # le total en R au fil des trades clôturés
        self.body.addWidget(self.curve)
        self.insights = Insights(journal)
        self.body.addWidget(self.insights)
        self.table = QTableWidget(0, len(COLUMNS), objectName="JournalTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)  # pas de cadre de focus case par case
        # Le style Windows 11 marque chaque case sélectionnée d'une barre : style neutre
        self._style = QStyleFactory.create("Fusion")
        self.table.setStyle(self._style)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.setMinimumHeight(260)  # une dizaine de trades visibles
        self.body.addWidget(self.table, 1)
        self.body.addLayout(self._actions())
        self.form = TradeForm(journal, snapshot, folder)
        self.form.added.connect(lambda _id: self.refresh())
        self.body.addWidget(self.form)
        self._confirm_delete: int | None = None
        self._seen = -1
        self._watch = QTimer(self, interval=1000)  # trade noté à la voix : mise à jour
        self._watch.timeout.connect(self._follow)
        self._watch.start()
        self.refresh()

    def _actions(self) -> QVBoxLayout:
        row = QHBoxLayout()
        self.exit_price = QLineEdit(placeholderText="Prix de sortie", objectName="JournalField")
        self.exit_price.setMaximumWidth(160)
        self.close_button = QPushButton("Clôturer", objectName="SettingsSmall")
        self.delete_button = QPushButton("Supprimer", objectName="SettingsSmall")
        export = QPushButton("Exporter (CSV)", objectName="SettingsSmall")
        self.close_button.clicked.connect(self.close_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        export.clicked.connect(self._export)
        self.notes = TradeNotes(self.journal)  # compléter le trade sélectionné
        self.note_button = QPushButton("Compléter", objectName="SettingsSmall")
        self.note_button.clicked.connect(self.annotate_selected)
        self.capture_button = QPushButton("Voir la capture", objectName="SettingsSmall")
        self.capture_button.clicked.connect(self.show_capture)
        self.message = QLabel(objectName="Hint", wordWrap=True)
        for widget in (self.exit_price, self.close_button, self.delete_button, self.capture_button):
            row.addWidget(widget)
        row.addWidget(self.message, 1)
        row.addWidget(export)
        notes = QHBoxLayout()  # 2e ligne : compléter le trade sélectionné
        notes.addWidget(QLabel("Compléter le trade choisi :", objectName="Hint"))
        notes.addWidget(self.notes, 1)
        notes.addWidget(self.note_button)
        column = QVBoxLayout()
        column.addLayout(row)
        column.addLayout(notes)
        return column

    def refresh(self) -> None:
        self._seen = self.journal.version
        self.stats.setText(stats_text(self.journal))
        self.curve.set_points(self.journal.equity())
        self.insights.refresh()
        self.notes.reload()
        trades = self.journal.all_trades()
        self.table.setRowCount(len(trades))
        for row, t in enumerate(trades):
            values = (t.id, t.opened_at.replace("T", " ")[:16], t.pair, t.direction, t.entry,
                      t.stop, t.target, planned_ratio(t), t.exit,
                      "" if t.result_r is None else f"{t.result_r:+.2f} R", t.setup,
                      {True: "oui", False: "non"}.get(t.plan_ok, ""), t.mood,
                      "📷" if t.capture else "", t.reason)  # fmt: skip
            for column, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else f"{value:g}"
                                        if isinstance(value, float) else str(value))  # fmt: skip
                item.setData(Qt.UserRole, t.id)
                if column == RESULT and t.result_r is not None:
                    item.setForeground(GAIN if t.result_r > 0 else LOSS)
                if column == len(COLUMNS) - 1:
                    item.setToolTip(t.reason)
                self.table.setItem(row, column, item)
        self._selected()

    def _follow(self) -> None:
        if self.journal.version != self._seen:
            self.refresh()

    def selected_trade(self) -> Trade | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        return self.journal.get(self.table.item(rows[0].row(), 0).data(Qt.UserRole))

    def _selected(self) -> None:
        trade = self.selected_trade()
        self._confirm_delete = None
        self.delete_button.setText("Supprimer")
        self.delete_button.setEnabled(trade is not None)
        self.close_button.setEnabled(trade is not None and trade.exit is None)
        self.exit_price.setEnabled(trade is not None and trade.exit is None)
        self.note_button.setEnabled(trade is not None)
        self.capture_button.setEnabled(trade is not None and bool(trade.capture))

    def annotate_selected(self) -> None:
        trade = self.selected_trade()
        if trade is None:
            return
        values = {k: v for k, v in self.notes.values().items() if v not in ("", None)}
        if not values:
            self.message.setText("⚠️ Choisissez le setup, le plan ou l'état d'esprit à noter.")
            return
        self.journal.annotate(trade.id, **values)
        self.notes.clear()
        self.message.setText(f"Trade n°{trade.id} complété.")
        self.refresh()

    def show_capture(self) -> None:
        trade = self.selected_trade()
        if trade is not None and trade.capture and Path(trade.capture).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(trade.capture))
        elif trade is not None:
            self.message.setText("⚠️ Capture introuvable sur ce PC.")

    def close_selected(self) -> None:
        trade = self.selected_trade()
        price = parse_price(self.exit_price.text()) if self.exit_price.text().strip() else None
        if trade is None or price is None or price <= 0:
            self.message.setText("⚠️ Choisissez un trade en cours et donnez son prix de sortie.")
            return
        closed = self.journal.close_trade(trade.id, price)
        self.exit_price.clear()
        self.message.setText(f"Trade n°{trade.id} clôturé : {closed.result_r:+.2f} R.")
        self.refresh()

    def delete_selected(self) -> None:
        trade = self.selected_trade()
        if trade is None:
            return
        if self._confirm_delete != trade.id:  # deux clics : on ne supprime pas par mégarde
            self._confirm_delete = trade.id
            self.delete_button.setText("Confirmer ?")
            return
        self.journal.delete_trade(trade.id)
        self.message.setText(f"Trade n°{trade.id} supprimé.")
        self.refresh()

    def _export(self) -> None:
        name, _ = QFileDialog.getSaveFileName(self, "Exporter le journal",
                                              "journal-trading.csv", "CSV (*.csv)")  # fmt: skip
        if name:
            count = self.journal.export_csv(Path(name))
            self.message.setText(f"{count} trade(s) exporté(s) dans {Path(name).name}.")
