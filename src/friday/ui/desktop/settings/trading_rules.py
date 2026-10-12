"""Réglages → Trading : « Gestion du risque et modèle « repli » ». La gestion du risque (stop
minimal, objectif, risque, trades ouverts, annonces, capital) vaut pour TOUTES les stratégies ;
tendance, repli et RSI ne règlent que le modèle « repli sur moyenne ». Gardés sur le PC
(data/trading_rules.json) ; pris en compte dès l'enregistrement."""

from dataclasses import fields

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from friday.trading.plan_rules import PlanRules, load_rules, save_rules

# champ : (libellé, minimum, maximum, pas) ; 0 désactive la règle quand c'est permis
FIELDS = {
    "stop_atr": ("Stop d'au moins (× ATR 1 h, 0 = sans)", 0, 10, 0.1),
    "min_rr": ("Objectif d'au moins (R, 0 = sans)", 0, 20, 0.5),
    "max_risk": ("Risque au plus (% du capital, 0 = sans)", 0, 100, 0.1),
    "max_open": ("Trades ouverts au plus (0 = sans)", 0, 50, 1),
    "news_minutes": ("Pas d'entrée si annonce forte dans (min, 0 = sans)", 0, 240, 5),
    "capital": ("Capital du compte (facultatif, reste sur ce PC)", 0, 1e9, 100),
    "trend_ema": ("Modèle « repli » : EMA de tendance journalière (0 = sans)", 0, 400, 10),
    "pullback_ema": ("Modèle « repli » : entrée près de l'EMA 1 h (0 = sans)", 0, 400, 10),
    "pullback_atr": ("… à moins de (× ATR 1 h)", 0.1, 10, 0.1),
    "rsi_low": ("Modèle « repli » : RSI 14 (1 h) à l'achat, de", 0, 100, 1),
    "rsi_high": ("… à (la vente : zone miroir)", 0, 100, 1),
}


class TradingRulesRow(QFrame):
    def __init__(self, rules_path) -> None:
        super().__init__(objectName="SettingsRow")
        self.rules_path = rules_path
        rules = load_rules(rules_path)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(QLabel("Gestion du risque et modèle « repli »",
                                objectName="SettingsLabel"))  # fmt: skip
        layout.addWidget(QLabel(
            "La gestion du risque vaut pour toutes les stratégies (check-list, backtest, "
            "alertes). Les lignes « Modèle « repli » » ne règlent que la stratégie de base du "
            "même nom.",
            objectName="Hint", wordWrap=True))  # fmt: skip
        form = QFormLayout()
        # Libellés longs à la ligne (constaté : 656 px de large, la page débordait)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.inputs = {}
        for name, (label, low, high, step) in FIELDS.items():
            box = QSpinBox() if isinstance(step, int) else QDoubleSpinBox(decimals=1)
            box.setRange(low, int(high) if isinstance(step, int) else high)
            box.setSingleStep(step)
            box.setValue(getattr(rules, name))
            form.addRow(QLabel(label, wordWrap=True), box)
            self.inputs[name] = box
        self.turning = QCheckBox("Le RSI doit repartir dans le sens du trade")
        self.turning.setChecked(rules.rsi_turning)
        form.addRow("", self.turning)
        layout.addLayout(form)
        line = QHBoxLayout()
        self.status = QLabel(objectName="Hint")
        line.addWidget(self.status, 1)
        save = QPushButton("Enregistrer les règles", objectName="SettingsSmall")
        save.setEnabled(rules_path is not None)
        save.clicked.connect(self.save)
        line.addWidget(save)
        layout.addLayout(line)
        self.setEnabled(rules_path is not None)

    def rules(self) -> PlanRules:
        kinds = {f.name: f.type for f in fields(PlanRules)}
        values = {n: (int if kinds[n] is int else float)(b.value())
                  for n, b in self.inputs.items()}  # fmt: skip
        return PlanRules(**values, rsi_turning=self.turning.isChecked())

    def save(self) -> None:
        rules = self.rules()
        if rules.rsi_low >= rules.rsi_high:
            self.status.setText("La zone du RSI doit aller du plus petit au plus grand.")
            return
        save_rules(self.rules_path, rules)
        self.status.setText("Règles enregistrées : prises en compte tout de suite.")
