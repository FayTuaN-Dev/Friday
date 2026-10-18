"""Les graphiques du bilan, en haut de l'onglet « Setups » : les courbes en R (tous, OUI et
NON de Claude), puis le total par marché et par stratégie. Cachés tant qu'aucun setup n'est
terminé (le texte du bilan dit alors d'attendre)."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from friday.trading.alerts.review import curves, totals_by
from friday.trading.instruments import by_symbol
from friday.ui.desktop.trading.result_bars import ResultBars
from friday.ui.desktop.trading.review_curves import ReviewCurves


def market(entry: dict) -> str:
    instrument = by_symbol(entry["symbol"])
    return instrument.name if instrument else entry["symbol"]


def strategy(entry: dict) -> str:
    return entry.get("label") or entry.get("strategy") or "?"


class ReviewCharts(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.curves = ReviewCurves()
        self.markets = ResultBars("Par marché")
        self.strategies = ResultBars("Par stratégie")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for widget in (self.curves, self.markets, self.strategies):
            layout.addWidget(widget)

    def refresh(self, entries: list[dict]) -> None:
        points = curves(entries)
        self.setVisible(bool(points))
        self.curves.set_points(points)
        self.markets.set_rows(totals_by(entries, market))
        self.strategies.set_rows(totals_by(entries, strategy))
