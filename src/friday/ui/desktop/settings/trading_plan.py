"""Réglages → Trading : « Mon plan de trading ». Claude jugera chaque idée au regard de ces
règles. Gardé sur le PC (data/trading_plan.txt) ; joint à une analyse seulement via l'aperçu,
masqué comme la question (montants, comptes…)."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from friday.trading.context_sources import PLAN_CHARS, load_plan, save_plan

PLACEHOLDER = (
    "Exemple :\n- Style : swing, graphiques 4 h et journalier.\n- Risque : 1 % par trade, "
    "3 trades ouverts au plus.\n- Entrée : cassure confirmée par une clôture 4 h, dans le sens "
    "de la MM200.\n- Sortie : stop sous le dernier creux, objectif à 2 R minimum.\n- Pas de "
    "trade 30 min avant une annonce à fort impact."
)


class TradingPlanRow(QFrame):
    def __init__(self, plan_path) -> None:
        super().__init__(objectName="SettingsRow")
        self.plan_path = plan_path
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(QLabel("Mon plan de trading", objectName="SettingsLabel"))
        layout.addWidget(QLabel(
            "Vos règles : Claude jugera chaque idée par rapport à elles. Restent sur ce PC ; "
            "jointes à une analyse via l'aperçu, masquées comme vos questions.",
            objectName="Hint", wordWrap=True))  # fmt: skip
        self.editor = QPlainTextEdit(placeholderText=PLACEHOLDER)
        self.editor.setMinimumHeight(150)
        self.editor.setEnabled(plan_path is not None)
        if plan_path is not None:
            self.editor.setPlainText(load_plan(plan_path))
        layout.addWidget(self.editor)
        line = QHBoxLayout()
        self.status = QLabel(objectName="Hint")
        line.addWidget(self.status, 1)
        save = QPushButton("Enregistrer le plan", objectName="SettingsSmall")
        save.setEnabled(plan_path is not None)
        save.clicked.connect(self.save)
        line.addWidget(save)
        layout.addLayout(line)

    def save(self) -> None:
        text = self.editor.toPlainText()
        save_plan(self.plan_path, text[:PLAN_CHARS])
        cut = " (coupé à 1 500 caractères)" if len(text) > PLAN_CHARS else ""
        self.status.setText(f"Plan enregistré{cut}.")
