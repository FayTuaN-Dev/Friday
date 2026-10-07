"""« Ce que dit le journal » : les constats calculés sur le PC (journal_stats.lessons) et, à
la demande, le détail par setup, instrument, heure, jour, plan et état d'esprit."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from friday.trading.journal import TradeJournal
from friday.trading.journal_stats import MIN_GROUP, breakdown, lessons

EMPTY = (f"Notez le setup, le respect du plan et votre état d'esprit : les constats apparaissent "
         f"dès {MIN_GROUP} trades clôturés par catégorie. Revue de la semaine par Claude : "
         "dites « fais ma revue de la semaine » (en mode trading, après aperçu).")  # fmt: skip


class Insights(QFrame):
    def __init__(self, journal: TradeJournal) -> None:
        super().__init__(objectName="JournalForm")
        self.journal = journal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        head = QHBoxLayout()
        head.addWidget(QLabel("Ce que dit le journal", objectName="SettingsLabel"), 1)
        self.toggle = QPushButton("Détail par catégorie", objectName="SettingsSmall")
        self.toggle.clicked.connect(self._toggle)
        head.addWidget(self.toggle)
        layout.addLayout(head)
        self.lessons = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.lessons)
        self.detail = QPlainTextEdit(readOnly=True)
        self.detail.setMinimumHeight(160)
        self.detail.hide()
        layout.addWidget(self.detail)

    def refresh(self) -> None:
        trades = self.journal.all_trades()
        found = lessons(trades)
        self.lessons.setText("\n".join(f"• {x}" for x in found) if found else EMPTY)
        self.detail.setPlainText(breakdown(trades))

    def _toggle(self) -> None:
        self.detail.setVisible(not self.detail.isVisible())
        self.toggle.setText("Masquer le détail" if self.detail.isVisible()
                            else "Détail par catégorie")  # fmt: skip
