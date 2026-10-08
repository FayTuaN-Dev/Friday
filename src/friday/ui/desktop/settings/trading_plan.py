"""Réglages → Trading : « Mes plans de trading », écrits librement — autant que tu veux. Chacun,
traduit en règles (par Claude, après aperçu), devient une stratégie : comparée aux autres,
choisie, suivie par le backtest, les alertes, la check-list et le briefing. Gardés sur le PC
(data/trading_plans.json) ; le plan suivi est joint aux analyses via l'aperçu, masqué."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from friday.trading.strategies.spec import describe

PLACEHOLDER = (
    "Exemple :\n- Style : intraday, graphique 1 h, dans le sens de l'EMA200 journalière.\n- "
    "Entrée : repli vers l'EMA50 1 h avec un RSI 14 entre 40 et 50 qui remonte.\n- Stop : sous "
    "le dernier creux ; objectif à 2 R.\n- Risque : 1 % par trade, 2 trades ouverts au plus.\n"
    "- Pas de trade 30 min avant une annonce à fort impact."
)
NOT_YET = ("Pas encore traduit en règles : « Traduire en règles » le fait comprendre par Claude "
           "(après aperçu).")  # fmt: skip


class TradingPlanRow(QFrame):
    def __init__(self, book, translate=None) -> None:
        """`book` : PlanBook ; `translate(nom)` : demande la traduction de ce plan (comme
        « traduis le plan … », donc avec l'aperçu habituel)."""
        super().__init__(objectName="SettingsRow")
        self.book, self.translate = book, translate
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(QLabel("Mes plans de trading", objectName="SettingsLabel"))
        layout.addWidget(QLabel(
            "Écris autant de stratégies que tu veux. « Traduire en règles » en fait une stratégie "
            "que Friday sait tester (« teste le plan … sur l'or »), comparer, suivre. Restent sur "
            "ce PC ; le plan suivi est joint aux analyses via l'aperçu, masqué.",
            objectName="Hint", wordWrap=True))  # fmt: skip
        top = QHBoxLayout()
        self.picker = QComboBox()
        self.picker.currentIndexChanged.connect(self._show)
        top.addWidget(self.picker, 1)
        self.delete_button = QPushButton("Supprimer", objectName="SettingsSmall")
        for text, action in (("Nouveau", self._new), ("Dupliquer", self._duplicate)):
            button = QPushButton(text, objectName="SettingsSmall")
            button.clicked.connect(action)
            top.addWidget(button)
        self.delete_button.clicked.connect(self._delete)
        top.addWidget(self.delete_button)
        layout.addLayout(top)
        self.name = QLineEdit(placeholderText="Nom du plan (ex. Cassure Londres)")
        layout.addWidget(self.name)
        self.editor = QPlainTextEdit(placeholderText=PLACEHOLDER)
        self.editor.setMinimumHeight(150)
        layout.addWidget(self.editor)
        line = QHBoxLayout()
        self.status = QLabel(objectName="Hint", wordWrap=True)
        line.addWidget(self.status, 1)
        save = QPushButton("Enregistrer", objectName="SettingsSmall")
        save.clicked.connect(self.save)
        line.addWidget(save)
        self.translate_button = QPushButton("Traduire en règles", objectName="SettingsSmall")
        self.translate_button.clicked.connect(self._translate)
        self.translate_button.setEnabled(translate is not None)
        line.addWidget(self.translate_button)
        layout.addLayout(line)
        self.rules = QLabel(objectName="Hint", wordWrap=True)
        layout.addWidget(self.rules)
        self._confirm_delete = False
        self.reload()
        self._watch = QTimer(self, interval=2000)  # la traduction arrive en arrière-plan
        self._watch.timeout.connect(self.refresh_rules)
        self._watch.start()

    def current(self) -> dict | None:
        return self.book.get(self.picker.currentData()) if self.picker.count() else None

    def reload(self, select: str | None = None) -> None:
        keep = select or self.picker.currentData()
        self.picker.blockSignals(True)
        self.picker.clear()
        for plan in self.book.plans():
            self.picker.addItem(plan["nom"] + (" ✅" if plan["spec"] else ""), plan["id"])
        self.picker.setCurrentIndex(max(0, self.picker.findData(keep)))
        self.picker.blockSignals(False)
        self._show()

    def save(self) -> None:
        plan = self.current()
        if plan is None:
            plan = self.book.add(self.name.text() or "Mon plan")
        self.book.update(plan["id"], nom=self.name.text(), texte=self.editor.toPlainText())
        self.reload(plan["id"])
        self.status.setText("Plan enregistré.")

    def refresh_rules(self) -> None:
        plan = self.current()
        if plan is None:
            self.rules.setText("Aucun plan : « Nouveau » pour en écrire un.")
            return
        if not plan["spec"]:
            self.rules.setText(NOT_YET)
            return
        edited = {**plan, "texte": self.editor.toPlainText()}
        if self.book.outdated(edited):
            head = f"⚠️ Plan modifié depuis la traduction du {plan['traduit_le']} : retraduisez-le."
        else:
            head = f"✅ Traduit le {plan['traduit_le']}. Ce que Friday a compris :"
        self.rules.setText("\n".join([head, *(f"• {line}" for line in describe(plan["spec"]))]))

    def _show(self) -> None:
        plan = self.current()
        self.name.setText(plan["nom"] if plan else "")
        self.editor.setPlainText(plan["texte"] if plan else "")
        self._confirm_delete = False
        self.delete_button.setText("Supprimer")
        self.delete_button.setEnabled(plan is not None)
        self.refresh_rules()

    def _new(self) -> None:
        plan = self.book.add("Nouveau plan")
        self.reload(plan["id"])
        self.status.setText("Nouveau plan : donne-lui un nom, écris-le, puis « Enregistrer ».")

    def _duplicate(self) -> None:
        plan = self.current()
        if plan is not None:
            copy = self.book.duplicate(plan["id"])
            self.reload(copy["id"])
            self.status.setText("Copie créée : modifie-la pour tester une variante.")

    def _delete(self) -> None:
        plan = self.current()
        if plan is None:
            return
        if not self._confirm_delete:  # deux clics : on ne supprime pas par mégarde
            self._confirm_delete = True
            self.delete_button.setText("Confirmer ?")
            return
        self.book.delete(plan["id"])
        self.reload()
        self.status.setText(f"Plan « {plan['nom']} » supprimé.")

    def _translate(self) -> None:
        self.save()
        plan = self.current()
        if plan is not None:
            self.translate(plan["nom"])
            self.status.setText("Traduction demandée : vérifie l'aperçu de l'envoi à Claude.")
