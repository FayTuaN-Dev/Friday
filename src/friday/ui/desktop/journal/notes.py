"""Les notes d'un trade, dans le formulaire et pour compléter un trade existant : setup
(proposés : ceux déjà utilisés), plan respecté ?, état d'esprit. C'est ce qui permet au
journal d'apprendre (journal_stats.py)."""

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from friday.trading.journal import TradeJournal
from friday.trading.journal_stats import MOODS

PLAN_CHOICES = ("Plan respecté ?", "oui", "non")
DEFAULT_SETUPS = ("repli EMA50 (plan)",)


def known_setups(journal: TradeJournal) -> list[str]:
    seen: dict[str, str] = {}
    for trade in journal.all_trades():
        if trade.setup:
            seen.setdefault(trade.setup.casefold(), trade.setup)
    for name in DEFAULT_SETUPS:
        seen.setdefault(name.casefold(), name)
    return list(seen.values())


class TradeNotes(QWidget):
    def __init__(self, journal: TradeJournal) -> None:
        super().__init__()
        self.journal = journal
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.setup = QComboBox(editable=True)
        self.setup.lineEdit().setPlaceholderText("Setup (repli EMA50, cassure…)")
        self.plan = QComboBox()
        self.plan.addItems(PLAN_CHOICES)
        self.mood = QComboBox(editable=True)
        self.mood.lineEdit().setPlaceholderText("État d'esprit")
        self.mood.addItems(MOODS)
        self.mood.setCurrentIndex(-1)  # vide : jamais « calme » par défaut (statistiques faussées)
        for widget in (self.setup, self.plan, self.mood):
            row.addWidget(widget, 1)
        self.reload()

    def reload(self) -> None:
        """Les setups déjà utilisés deviennent des choix (on écrit pareil : stats justes)."""
        current = self.setup.currentText()
        self.setup.clear()
        self.setup.addItems(known_setups(self.journal))
        self.setup.setEditText(current)

    def values(self) -> dict:
        plan = {"oui": True, "non": False}.get(self.plan.currentText())
        return {"setup": self.setup.currentText().strip(), "plan_ok": plan,
                "mood": self.mood.currentText().strip()}  # fmt: skip

    def clear(self) -> None:
        self.setup.setEditText("")
        self.plan.setCurrentIndex(0)
        self.mood.setEditText("")
