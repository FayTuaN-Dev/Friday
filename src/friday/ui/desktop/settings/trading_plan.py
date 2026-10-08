"""Réglages → Trading : « Mon plan de trading », écrit librement. Traduit en règles (par
Claude, après aperçu), il devient TA stratégie : backtest, alertes, check-list, briefing.
Gardé sur le PC (data/trading_plan.txt) ; joint à une analyse seulement via l'aperçu, masqué
comme une question (montants, comptes…)."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from friday.trading.context_sources import PLAN_CHARS, load_plan, save_plan
from friday.trading.strategies.spec import describe

PLACEHOLDER = (
    "Exemple :\n- Style : intraday, graphique 1 h, dans le sens de l'EMA200 journalière.\n- "
    "Entrée : repli vers l'EMA50 1 h avec un RSI 14 entre 40 et 50 qui remonte.\n- Stop : sous "
    "le dernier creux ; objectif à 2 R.\n- Risque : 1 % par trade, 2 trades ouverts au plus.\n"
    "- Pas de trade 30 min avant une annonce à fort impact."
)
NOT_YET = ("Pas encore traduit en règles : tant qu'il ne l'est pas, Friday utilise le modèle "
           "« repli sur moyenne ».")  # fmt: skip


class TradingPlanRow(QFrame):
    def __init__(self, plan_path, choice=None, translate=None) -> None:
        """`choice` : StrategyChoice (règles traduites) ; `translate()` : demande la traduction
        (comme « traduis mon plan », donc avec l'aperçu habituel)."""
        super().__init__(objectName="SettingsRow")
        self.plan_path, self.choice, self.translate = plan_path, choice, translate
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(QLabel("Mon plan de trading", objectName="SettingsLabel"))
        layout.addWidget(QLabel(
            "Votre stratégie, écrite librement. « Traduire en règles » la fait comprendre par "
            "Claude (après aperçu) : elle sert alors au backtest, aux alertes, à la check-list "
            "et au briefing. Reste sur ce PC ; jointe à une analyse via l'aperçu, masquée.",
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
        self.translate_button = QPushButton("Traduire en règles", objectName="SettingsSmall")
        self.translate_button.setEnabled(plan_path is not None and translate is not None)
        self.translate_button.clicked.connect(self._translate)
        line.addWidget(self.translate_button)
        layout.addLayout(line)
        self.rules = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.rules)
        self.refresh_rules()
        self._watch = QTimer(self, interval=2000)  # la traduction arrive en arrière-plan
        self._watch.timeout.connect(self.refresh_rules)
        self._watch.start()

    def save(self) -> None:
        text = self.editor.toPlainText()
        save_plan(self.plan_path, text[:PLAN_CHARS])
        cut = " (coupé à 1 500 caractères)" if len(text) > PLAN_CHARS else ""
        self.status.setText(f"Plan enregistré{cut}.")

    def refresh_rules(self) -> None:
        found = self.choice.translated() if self.choice is not None else None
        if found is None:
            self.rules.setText(NOT_YET)
            return
        if self.choice.outdated(self.editor.toPlainText()):
            head = f"⚠️ Plan modifié depuis la traduction du {found['traduit_le']} : retraduisez-le."
        else:
            head = f"✅ Traduit le {found['traduit_le']}. Ce que Friday a compris :"
        lines = [f"• {line}" for line in describe(found["spec"])]
        self.rules.setText("\n".join([head, *lines]))

    def _translate(self) -> None:
        self.save()
        self.translate()
        self.status.setText("Traduction demandée : vérifiez l'aperçu de l'envoi à Claude.")
