"""Les réglages (U7) : un panneau dans la fenêtre de Friday (overlay.py), menu en groupes à
gauche, une page par thème. La couleur, le cœur, le briefing et le compte Google
s'appliquent tout de suite ; les réglages du .env demandent un redémarrage : une barre
n'apparaît qu'en cas de modification (« Annuler » · « Enregistrer »), puis propose de
redémarrer."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
)

from friday.core.env_file import read_env, update_env
from friday.core.settings_schema import SECTIONS
from friday.ui.desktop import theme
from friday.ui.desktop.icons import icon
from friday.ui.desktop.settings.briefing_page import BriefingPage
from friday.ui.desktop.settings.diagnostic_page import DiagnosticPage
from friday.ui.desktop.settings.form_page import FormPage
from friday.ui.desktop.settings.library_page import LibraryPage
from friday.ui.desktop.settings.other_pages import AccountsPage, AppearancePage
from friday.ui.desktop.settings.trading_plan import TradingPlanRow
from friday.ui.desktop.settings.trading_rules import TradingRulesRow
from friday.ui.desktop.settings.trading_strategy import StrategyRow
from friday.ui.desktop.settings.zone_picker import chart_zone_widget

# Le menu, en groupes : (groupe, pages)
GROUPS = (("Friday", ("Apparence", "Général", "Voix", "Écoute")),
          ("Services", ("Fonctions", "Briefing", "Bibliothèque", "Comptes")),
          ("Trading", ("Trading",)), ("Système", ("Diagnostic",)))  # fmt: skip
COMPACT_BELOW = 760  # panneau plus étroit : le menu n'a plus que ses icônes
ICONS = {"Apparence": "palette", "Général": "user", "Voix": "volume", "Écoute": "mic",
         "Fonctions": "sliders", "Briefing": "sun", "Bibliothèque": "book", "Comptes": "cloud",
         "Trading": "trending", "Diagnostic": "pulse"}  # fmt: skip


class SettingsWindow(QFrame):
    def __init__(self, main_window) -> None:
        """`main_window` : pour appliquer la couleur, joindre l'assistant et redémarrer."""
        super().__init__(objectName="SettingsCard")
        self.setAttribute(Qt.WA_StyledBackground)
        self.main_window = main_window
        self._saved = False  # enregistré, redémarrage pas encore fait
        components = main_window.assistant.components
        env = read_env()
        self.forms = [FormPage(section, env) for section in SECTIONS]
        by_name = {form_section.name: form for form_section, form in zip(SECTIONS, self.forms,
                                                                        strict=True)}  # fmt: skip
        for form in self.forms:
            form.edited.connect(self._refresh_bar)
        pages = {
            "Apparence": AppearancePage(main_window.base, main_window.apply_color,
                                        main_window.orb_style, main_window.set_orb_style),
            "Général": by_name["Général"], "Voix": by_name["Voix"], "Écoute": by_name["Écoute"],
            "Briefing": BriefingPage(getattr(components, "briefing", None)),
            "Bibliothèque": LibraryPage(getattr(components, "library", None)),
            "Fonctions": by_name["Fonctions"],
            "Trading": self._trading_page(by_name["Trading"], components),
            "Comptes": AccountsPage(getattr(components, "google", None)),
            "Diagnostic": DiagnosticPage(main_window.assistant, main_window.settings,
                                         refresh_now=False),  # bilan à l'ouverture de la page
        }  # fmt: skip
        self.nav = QListWidget(objectName="SettingsNav")
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setFixedWidth(190)
        self.stack = QStackedWidget()
        accent = theme.current().accent
        for group, names in GROUPS:
            header = QListWidgetItem(group.upper(), self.nav)
            header.setFlags(Qt.NoItemFlags)  # un titre de groupe : ni cliquable ni choisi
            header.setData(Qt.UserRole, None)
            for name in names:
                item = QListWidgetItem(icon(ICONS[name], accent, 18), name, self.nav)
                item.setData(Qt.UserRole, self.stack.count())
                item.setData(Qt.UserRole + 1, name)
                scroll = QScrollArea(widgetResizable=True)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # rien ne déborde
                scroll.setWidget(pages[name])
                self.stack.addWidget(scroll)
        self.nav.currentItemChanged.connect(self._show_page)
        self.nav.setCurrentRow(1)  # « Apparence » (la ligne 0 est le titre « FRIDAY »)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(self._header())
        middle = QHBoxLayout()
        middle.setSpacing(16)
        middle.addWidget(self.nav)
        middle.addWidget(self.stack, 1)
        layout.addLayout(middle, 1)
        layout.addWidget(self._save_bar())

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        title = QLabel("RÉGLAGES", objectName="SettingsHeader")
        close = QPushButton(objectName="PopupClose", toolTip="Fermer (Échap)")
        close.setIcon(icon("close", theme.current().muted, 14))
        close.setIconSize(QSize(14, 14))
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        row.addWidget(title, 1)
        row.addWidget(close)
        return row

    def resizeEvent(self, event) -> None:
        """Panneau étroit : menu réduit à ses icônes (le nom en bulle), titres de groupe
        cachés ; les pages reprennent la place."""
        super().resizeEvent(event)
        compact = self.width() < COMPACT_BELOW
        if compact == getattr(self, "_compact", None):
            return
        self._compact = compact
        self.nav.setFixedWidth(58 if compact else 190)
        for row in range(self.nav.count()):
            item = self.nav.item(row)
            if item.data(Qt.UserRole) is None:
                item.setHidden(compact)
                continue
            name = item.data(Qt.UserRole + 1) or item.text()
            item.setData(Qt.UserRole + 1, name)
            item.setText("" if compact else name)
            item.setToolTip(name if compact else "")

    def _show_page(self, item) -> None:
        if item is not None and item.data(Qt.UserRole) is not None:
            self.stack.setCurrentIndex(item.data(Qt.UserRole))
            page = self.stack.currentWidget().widget()
            if hasattr(page, "refresh_async"):  # Diagnostic : le bilan, sans figer Friday
                page.refresh_async()

    def refresh_icons(self, accent: str) -> None:
        """La couleur de Friday change : les icônes du menu suivent (le panneau est gardé)."""
        for row in range(self.nav.count()):
            item = self.nav.item(row)
            name = item.data(Qt.UserRole + 1) or item.text()
            if item.data(Qt.UserRole) is not None and name in ICONS:
                item.setIcon(icon(ICONS[name], accent, 18))

    def show_page(self, name: str) -> None:
        """Ouvre une page par son nom (« Trading »…)."""
        for row in range(self.nav.count()):
            item = self.nav.item(row)
            if name in (item.text(), item.data(Qt.UserRole + 1)):
                self.nav.setCurrentRow(row)

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
        """« Traduire en règles » : comme le dire (plus besoin du mode trading)."""
        self.main_window.assistant.submit_text(f"traduis le plan {name}")

    def _save_bar(self) -> QFrame:
        """Cachée tant que rien n'a changé ; « Redémarrer » une fois enregistré."""
        self.bar = QFrame(objectName="SaveBar")
        row = QHBoxLayout(self.bar)
        row.setContentsMargins(16, 8, 8, 8)
        self.banner = QLabel(objectName="SaveBarText", wordWrap=True)
        self.cancel_button = QPushButton("Annuler", objectName="SettingsSmall")
        self.save_button = QPushButton("Enregistrer", objectName="SettingsPrimary")
        self.restart_button = QPushButton("Redémarrer Friday", objectName="SettingsPrimary")
        self.cancel_button.clicked.connect(self.revert)
        self.save_button.clicked.connect(self.save)
        self.restart_button.clicked.connect(self.main_window.restart)
        row.addWidget(self.banner, 1)
        for button in (self.cancel_button, self.save_button, self.restart_button):
            row.addWidget(button, 0, Qt.AlignRight)
        self._refresh_bar()
        return self.bar

    def _refresh_bar(self) -> None:
        count = len(self.changes())
        plural = "s" if count > 1 else ""
        if count:
            self.banner.setText(f"{count} réglage{plural} modifié{plural}")
        elif self._saved:
            self.banner.setText("Enregistré : redémarrez Friday pour l'appliquer.")
        self.cancel_button.setVisible(bool(count))
        self.save_button.setVisible(bool(count))
        self.restart_button.setVisible(self._saved and not count)
        self.bar.setVisible(bool(count) or self._saved)

    def revert(self) -> None:
        for form in self.forms:
            form.revert()
        self._refresh_bar()

    def close(self) -> bool:
        """Le panneau repart vers la droite (overlay.py), puis il est caché (gardé pour la
        prochaine fois : le reconstruire figeait Friday)."""
        overlay = self.parent()
        if overlay is not None and hasattr(overlay, "dismiss"):
            overlay.dismiss()
        else:
            self.deleteLater()
        return True

    def changes(self) -> dict[str, str]:
        changed: dict[str, str] = {}
        for form in self.forms:
            changed |= form.changes()
        return changed

    def save(self) -> bool:
        """Écrit les réglages modifiés dans le .env ; renvoie True s'il y en avait."""
        changed = self.changes()
        if not changed:
            return False
        update_env(changed)
        for form in self.forms:  # les nouvelles valeurs deviennent le point de départ
            form.commit()
        self._saved = True
        self._refresh_bar()
        return True
