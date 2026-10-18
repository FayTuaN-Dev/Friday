"""Page Trading → « Réglages » : tout ce qui touchait au trading dans les Réglages de Friday,
réuni ici. Les réglages du .env (devise, heures, briefing…), avec leur propre barre
« Enregistrer », puis la zone du graphique, la stratégie suivie, les plans et les règles."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from friday.core.env_file import read_env
from friday.core.settings_schema import SECTIONS
from friday.ui.desktop.settings.form_page import FormPage
from friday.ui.desktop.settings.save_bar import SaveBar
from friday.ui.desktop.settings.trading_plan import TradingPlanRow
from friday.ui.desktop.settings.trading_rules import TradingRulesRow
from friday.ui.desktop.settings.trading_strategy import StrategyRow
from friday.ui.desktop.settings.zone_picker import chart_zone_widget


class TradingSettings(QWidget):
    def __init__(self, trading, restart, translate=None) -> None:
        """`restart` : relance Friday ; `translate(nom)` : « Traduire en règles » un plan."""
        super().__init__()
        section = next(s for s in SECTIONS if s.name == "Trading")
        self.form = FormPage(section, read_env())
        self.form.add_extra(chart_zone_widget(getattr(trading, "capture", None)))
        choice = getattr(trading, "choice", None)
        self.form.add_extra(StrategyRow(choice))
        if choice is not None:
            self.form.add_extra(TradingPlanRow(choice.book, translate))
        self.form.add_extra(TradingRulesRow(getattr(trading, "rules_path", None)))
        scroll = QScrollArea(widgetResizable=True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # très étroit : rien de caché
        scroll.setWidget(self.form)
        self.bar = SaveBar([self.form], restart)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.bar)
