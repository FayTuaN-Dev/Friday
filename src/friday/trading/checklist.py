"""Check-list avant trade : l'idée de trade, les données, et le verdict règle par règle. Les
règles du plan (plan_rules.py) sont vérifiées par le CODE (plan_checks.py) sur une idée de
trade (« acheter l'or à 4 160, stop 4 140 »). Rien n'est confié au modèle ni à Claude.

Chaque règle donne ✅ respectée, ❌ enfreinte, ou ❔ invérifiable (donnée manquante : objectif,
capital, calendrier en panne…). Feu rouge dès qu'une règle est enfreinte ; orange s'il en reste
d'invérifiables ; vert sinon. Ce n'est jamais un signal : seulement « ton plan est-il respecté ».
"""

from dataclasses import dataclass, field
from datetime import datetime

from friday.trading.calendar import Event
from friday.trading.instruments import Instrument
from friday.trading.market import Candle

OK, KO, UNKNOWN = "ok", "ko", "?"
ICONS = {OK: "✅", KO: "❌", UNKNOWN: "❔"}


@dataclass
class Idea:
    instrument: Instrument
    direction: str  # « achat » ou « vente »
    entry: float
    stop: float
    target: float | None = None
    risk_percent: float | None = None
    lots: float | None = None

    @property
    def buy(self) -> bool:
        return self.direction == "achat"

    def check_sides(self) -> None:
        """Stop et objectif du bon côté de l'entrée, sinon ValueError (message clair)."""
        trade, below, above = ("un achat", "sous", "au-dessus de") if self.buy else (
            "une vente", "au-dessus de", "sous")  # fmt: skip
        if self.stop == self.entry:
            raise ValueError("Le stop ne peut pas être au prix d'entrée.")
        if (self.stop < self.entry) != self.buy:
            raise ValueError(f"Pour {trade}, le stop doit être {below} l'entrée.")
        if self.target is not None and (self.target > self.entry) != self.buy:
            raise ValueError(f"Pour {trade}, l'objectif doit être {above} l'entrée.")


@dataclass
class Market:
    """Cours Yahoo. `shift` : écart contrat à terme − cours du graphique (0 sinon) ;
    `shift_known` : faux pour un contrat à terme dont le graphique n'est pas visible."""

    price: float
    daily: list[Candle]
    hourly: list[Candle]
    shift: float = 0.0
    shift_known: bool = True


@dataclass
class Context:
    now: datetime
    events: list[Event] | None = None  # annonces de la semaine ; None : calendrier en panne
    open_trades: int | None = None  # trades ouverts au journal
    value_per_lot: float | None = None  # valeur d'un pip / point pour 1 lot (devise du compte)
    account: str = "EUR"


@dataclass
class Check:
    rule: str
    status: str
    detail: str


@dataclass
class Verdict:
    checks: list[Check] = field(default_factory=list)

    @property
    def light(self) -> str:
        statuses = {c.status for c in self.checks}
        return "rouge" if KO in statuses else "orange" if UNKNOWN in statuses else "vert"

    def text(self) -> str:
        broken = [c.rule for c in self.checks if c.status == KO]
        missing = [c.rule for c in self.checks if c.status == UNKNOWN]
        head = {
            "rouge": f"🔴 Feu rouge : {len(broken)} règle(s) du plan enfreinte(s) "
                     f"({', '.join(broken)}).",
            "orange": f"🟠 Feu orange : rien d'enfreint, mais à vérifier ({', '.join(missing)}).",
            "vert": "🟢 Feu vert : toutes les règles du plan sont respectées.",
        }[self.light]  # fmt: skip
        lines = [f"{ICONS[c.status]} {c.rule} : {c.detail}" for c in self.checks]
        return head + "\n" + "\n".join(lines)
