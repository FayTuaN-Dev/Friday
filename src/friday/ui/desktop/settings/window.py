"""Fenêtre des réglages : menu à gauche, une page par thème. Les réglages du .env demandent un
redémarrage (bouton dédié) ; la couleur, le briefing et le compte Google s'appliquent tout
de suite."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
)

from friday.core.env_file import read_env, update_env
from friday.core.settings_schema import SECTIONS
from friday.ui.desktop import theme
from friday.ui.desktop.icons import icon
from friday.ui.desktop.popups.base import Popup
from friday.ui.desktop.settings.briefing_page import BriefingPage
from friday.ui.desktop.settings.diagnostic_page import DiagnosticPage
from friday.ui.desktop.settings.form_page import FormPage
from friday.ui.desktop.settings.library_page import LibraryPage
from friday.ui.desktop.settings.other_pages import AccountsPage, AppearancePage
from friday.ui.desktop.settings.trading_plan import TradingPlanRow
from friday.ui.desktop.settings.trading_rules import TradingRulesRow
from friday.ui.desktop.settings.trading_strategy import StrategyRow
from friday.ui.desktop.settings.zone_picker import chart_zone_widget

SIZE = (840, 620)


class SettingsWindow(Popup):
    def __init__(self, main_window) -> None:
        """`main_window` : pour appliquer la couleur, joindre l'assistant et redémarrer."""
        super().__init__("⚙️", "Réglages", SIZE)
        self.main_window = main_window
        components = main_window.assistant.components
        env = read_env()
        self.forms = [FormPage(section, env) for section in SECTIONS]
        by_name = {form_section.name: form for form_section, form in zip(SECTIONS, self.forms,
                                                                        strict=True)}  # fmt: skip
        pages = [
            (
                "Apparence",
                "palette",
                AppearancePage(
                    main_window.base,
                    main_window.apply_color,
                    main_window.orb_style,
                    main_window.set_orb_style,
                ),
            ),
            ("Général", "user", by_name["Général"]),
            ("Voix", "volume", by_name["Voix"]),
            ("Écoute", "mic", by_name["Écoute"]),
            ("Briefing", "sun", BriefingPage(getattr(components, "briefing", None))),
            ("Bibliothèque", "book", LibraryPage(getattr(components, "library", None))),
            ("Fonctions", "sliders", by_name["Fonctions"]),
            ("Trading", "trending", self._trading_page(by_name["Trading"], components)),
            ("Comptes", "cloud", AccountsPage(getattr(components, "google", None))),
            ("Diagnostic", "pulse", DiagnosticPage(main_window.assistant, main_window.settings)),
        ]
        self.nav = QListWidget(objectName="SettingsNav")
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setFixedWidth(180)
        self.stack = QStackedWidget()
        accent = theme.current().accent
        for name, icon_name, page in pages:
            QListWidgetItem(icon(icon_name, accent, 18), name, self.nav)
            scroll = QScrollArea(widgetResizable=True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        middle = QHBoxLayout()
        middle.setSpacing(14)
        middle.addWidget(self.nav)
        middle.addWidget(self.stack, 1)
        self.body.addLayout(middle, 1)
        self.body.addLayout(self._footer())

    def _trading_page(self, form: FormPage, components) -> FormPage:
        trading = getattr(components, "trading", None)
        journal = QPushButton("Ouvrir le journal de trading", objectName="SettingsSmall")
        journal.setEnabled(trading is not None)
        journal.clicked.connect(self.main_window.open_journal)
        form.add_extra(journal)
        form.add_extra(chart_zone_widget(getattr(trading, "capture", None)))
        choice = getattr(trading, "choice", None)
        form.add_extra(StrategyRow(choice))
        translate = self._translate_plan if getattr(trading, "translator", None) else None
        if choice is not None:
            form.add_extra(TradingPlanRow(choice.book, translate))
        form.add_extra(TradingRulesRow(getattr(trading, "rules_path", None)))
        return form

    def _translate_plan(self, name: str) -> None:
        """« Traduire en règles » : comme le dire (passe d'abord en mode trading s'il le faut)."""
        assistant = self.main_window.assistant
        trading = getattr(assistant.components, "trading", None)
        if trading is not None and not trading.mode.enabled:
            assistant.submit_text("mode trading")
        assistant.submit_text(f"traduis le plan {name}")

    def _footer(self) -> QHBoxLayout:
        self.banner = QLabel(objectName="Hint", wordWrap=True)
        self.save_button = QPushButton("Enregistrer", objectName="SettingsPrimary")
        self.restart_button = QPushButton("Redémarrer Friday", objectName="SettingsPrimary")
        self.restart_button.hide()
        close = QPushButton("Fermer", objectName="SettingsSmall")
        self.save_button.clicked.connect(self.save)
        self.restart_button.clicked.connect(self.main_window.restart)
        close.clicked.connect(self.close)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 10, 0, 0)
        footer.addWidget(self.banner, 1)
        for button in (close, self.save_button, self.restart_button):
            footer.addWidget(button, 0, Qt.AlignRight)
        return footer

    def changes(self) -> dict[str, str]:
        changed: dict[str, str] = {}
        for form in self.forms:
            changed |= form.changes()
        return changed

    def save(self) -> bool:
        """Écrit les réglages modifiés dans le .env ; renvoie True s'il y en avait."""
        changed = self.changes()
        if not changed:
            self.banner.setText(
                "Aucun réglage modifié (la couleur et le briefing sont déjà appliqués)."
            )
            return False
        update_env(changed)
        for form in self.forms:  # les nouvelles valeurs deviennent le point de départ
            form.commit()
        self.banner.setText(f"{len(changed)} réglage(s) enregistré(s) : redémarrez Friday pour "
                            "les appliquer.")  # fmt: skip
        self.restart_button.show()
        return True
