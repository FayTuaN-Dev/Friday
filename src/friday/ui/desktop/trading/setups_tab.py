"""Page Trading → « Setups » : le carnet des setups de la surveillance des marchés. En haut,
le bilan (ce que les setups fermés auraient donné : tous, ceux où Claude a dit OUI, ceux où
il a dit NON) ; puis chaque setup, le plus récent d'abord, avec l'avis de Claude et ce que le
trade aurait donné. Un clic sur une ligne montre l'annonce faite et la raison de Claude."""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from friday.trading.alerts.review import review
from friday.trading.alerts.setup_log import PENDING
from friday.trading.backtest.report import FEW, r_text
from friday.trading.instruments import by_symbol
from friday.trading.market import _digits
from friday.ui.desktop.journal.window import GAIN, LOSS

COLUMNS = ("Vu le", "Marché", "Sens", "Stratégie", "Entrée", "Stop", "Objectif",
           "Avis de Claude", "Résultat")  # fmt: skip
VERDICT, RESULT = COLUMNS.index("Avis de Claude"), COLUMNS.index("Résultat")
FILTERS = {
    "Tous les setups": lambda e: True,
    "Claude a dit OUI": lambda e: e.get("avis") == "oui",
    "Claude a dit NON": lambda e: e.get("avis") == "non",
    "En cours": lambda e: e["result_r"] is None,
    "Terminés": lambda e: e["result_r"] is not None,
}
EMPTY = (
    "Aucun setup noté pour l'instant. Dites « surveille tous les marchés » : chaque "
    "setup trouvé s'inscrira ici, avec l'avis de Claude s'il est activé (Réglages)."
)


def verdict_word(entry: dict) -> str:
    avis = entry.get("avis")
    return {"oui": "OUI", "non": "NON", PENDING: "en attente"}.get(avis, "—")


def result_word(entry: dict) -> str:
    return "en cours" if entry["result_r"] is None else f"{entry['result_r']:+.2f} R"


def review_text(entries: list[dict]) -> tuple[str, str]:
    """(le titre : combien de setups et ce qu'ils rapportent, le détail par avis de Claude)."""
    if not entries:
        return EMPTY, ""
    reports, running = review(entries)
    whole = reports[0]
    later = f" · {running} en cours" if running else ""
    if not whole.count:
        return f"{len(entries)} setup(s) noté(s), aucun terminé{later}", ""
    title = f"{whole.count} setup(s) terminé(s) : {r_text(whole.expectancy)} par trade{later}"
    lines = [f"{r.label} : {r.short()}" for r in reports[1:] if r.count]
    if whole.count < FEW:
        lines.append(f"Moins de {FEW} setups terminés : trop tôt pour conclure.")
    return title, "\n".join(lines)


def _price(symbol: str, value) -> str:
    if value is None:
        return "—"
    instrument = by_symbol(symbol)
    return f"{value:.{_digits(instrument)}f}" if instrument else f"{value:g}"


def row_values(entry: dict) -> tuple[str, ...]:
    instrument = by_symbol(entry["symbol"])
    seen = datetime.fromisoformat(entry["seen"])
    target = (_price(entry["symbol"], entry["target"]) if entry["target"] is not None
              else f"suiveuse ({entry['trail']})" if entry.get("trail") else "—")  # fmt: skip
    return (f"{seen:%d/%m %H:%M}", instrument.name if instrument else entry["symbol"],
            entry["side"], entry.get("label") or entry.get("strategy", ""),
            _price(entry["symbol"], entry["close"]), _price(entry["symbol"], entry["stop"]),
            target, verdict_word(entry), result_word(entry))  # fmt: skip


class SetupsView(QWidget):
    def __init__(self, setups) -> None:
        """`setups` : le SetupLog de la surveillance (None : trading désactivé)."""
        super().__init__(objectName="SettingsPage")
        self.setups = setups
        self.summary = QLabel(objectName="SettingsTitle", wordWrap=True)
        self.review = QLabel(objectName="Hint", wordWrap=True)
        self.filter = QComboBox()
        self.filter.addItems(list(FILTERS))
        self.filter.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.table = self._table()
        self.detail = QLabel(objectName="Hint", wordWrap=True)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row = QHBoxLayout()
        row.addWidget(QLabel("Afficher :", objectName="Hint"))
        row.addWidget(self.filter)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(10)
        layout.addWidget(self.summary)
        layout.addWidget(self.review)
        layout.addLayout(row)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.detail)
        self._seen = None  # le carnet affiché (les ids, avis et résultats)
        self._watch = QTimer(self, interval=2000)  # setup trouvé, avis arrivé : mise à jour
        self._watch.timeout.connect(self._follow)
        self._watch.start()
        self.refresh()

    def _table(self) -> QTableWidget:
        table = QTableWidget(0, len(COLUMNS), objectName="JournalTable")
        table.setHorizontalHeaderLabels(COLUMNS)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.NoFocus)
        self._style = QStyleFactory.create("Fusion")  # comme le journal : sélection neutre
        table.setStyle(self._style)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)
        table.setMinimumHeight(260)
        table.itemSelectionChanged.connect(self._selected)
        return table

    def entries(self) -> list[dict]:
        return self.setups.all() if self.setups is not None else []

    def _follow(self) -> None:
        if self.isVisible():
            self.refresh()

    def refresh(self, force: bool = False) -> None:
        entries = self.entries()
        seen = [(e["id"], e.get("avis"), e["result_r"]) for e in entries]
        if seen == self._seen and not force:
            return
        self._seen = seen
        title, detail = review_text(entries)
        self.summary.setText(title)
        self.review.setText(detail)
        self.review.setVisible(bool(detail))
        keep = FILTERS[self.filter.currentText()]
        shown = sorted((e for e in entries if keep(e)), key=lambda e: e["seen"], reverse=True)
        self.table.setRowCount(len(shown))
        for row, entry in enumerate(shown):
            for column, value in enumerate(row_values(entry)):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, entry["id"])
                if column == RESULT and entry["result_r"] is not None:
                    item.setForeground(GAIN if entry["result_r"] > 0 else LOSS)
                if column == VERDICT and entry.get("avis") in ("oui", "non"):
                    item.setForeground(GAIN if entry["avis"] == "oui" else LOSS)
                    item.setToolTip(entry.get("raison", ""))
                self.table.setItem(row, column, item)
        self._selected()

    def selected(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        wanted = self.table.item(rows[0].row(), 0).data(Qt.UserRole)
        return next((e for e in self.entries() if e["id"] == wanted), None)

    def _selected(self) -> None:
        entry = self.selected()
        if entry is None:
            self.detail.setText("Cliquez sur un setup pour revoir son annonce et l'avis de "
                                "Claude." if self.table.rowCount() else "")  # fmt: skip
            return
        text = entry["text"]
        if entry.get("avis") in ("oui", "non"):
            text += f"\n\nAvis de Claude : {verdict_word(entry)}. {entry.get('raison', '')}"
        if entry.get("closed"):
            closed = datetime.fromisoformat(entry["closed"])
            text += f"\n\nTerminé le {closed:%d/%m à %H:%M} : {result_word(entry)}."
        self.detail.setText(text)
