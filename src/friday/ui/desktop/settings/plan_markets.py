"""Réglages → Trading → Mes plans : les familles de marchés qu'un plan suit (devises, matières
premières, indices, crypto, actions), à cocher. Constaté sur 20 ans : Turtle gagne sur les
matières et les indices mais perd sur les devises depuis 2016 ; la crypto, à part, se coche ou
se décoche. Un plan qui ne suit pas un marché n'y est ni comparé, ni surveillé."""

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from friday.trading.instruments import FAMILIES


class PlanMarkets(QWidget):
    def __init__(self, book) -> None:
        super().__init__()
        self.book, self.plan_id = book, None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Marchés suivis :", objectName="Hint"))
        self.boxes: dict[str, QCheckBox] = {}
        for key, label in FAMILIES.items():
            box = QCheckBox(label)
            box.toggled.connect(self._changed)
            layout.addWidget(box)
            self.boxes[key] = box
        layout.addStretch(1)

    def show_plan(self, plan: dict | None) -> None:
        self.plan_id = plan["id"] if plan else None
        chosen = plan.get("familles") if plan else None
        for key, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(chosen is None or key in chosen)
            box.setEnabled(plan is not None)
            box.blockSignals(False)

    def chosen(self) -> list[str] | None:
        """Les familles cochées ; None : toutes (le plan suit tous les marchés)."""
        ticked = [key for key, box in self.boxes.items() if box.isChecked()]
        return None if len(ticked) == len(self.boxes) else ticked

    def _changed(self) -> None:
        if self.plan_id is not None:
            self.book.set_families(self.plan_id, self.chosen())
