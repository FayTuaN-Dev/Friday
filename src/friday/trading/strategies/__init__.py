"""La bibliothèque de stratégies (T7) : chacune est une règle d'entrée sur la clôture d'une
bougie 1 h (base.py) ; le moteur, la gestion du risque, les alertes et la check-list sont
communs. Ajouter une stratégie : une classe ici, enregistrée dans STRATEGIES."""

from friday.trading.strategies.base import Entry, State, Strategy, finished_day
from friday.trading.strategies.plan import PlanStrategy
from friday.trading.strategies.reversion import ReversionStrategy
from friday.trading.strategies.session import LondonOpenStrategy
from friday.trading.strategies.trend import BreakoutStrategy, CrossoverStrategy
from friday.voice.wake import normalize

STRATEGIES: tuple[Strategy, ...] = (PlanStrategy(), CrossoverStrategy(), BreakoutStrategy(),
                                    ReversionStrategy(), LondonOpenStrategy())  # fmt: skip
BY_NAME = {s.name: s for s in STRATEGIES}

__all__ = ["BY_NAME", "STRATEGIES", "Entry", "State", "Strategy", "finished_day", "strategy_named"]

# Mots qui désignent chaque stratégie (Londres avant « cassure » : « cassure de l'ouverture… »)
WORDS = (("londres", ("londres", "ouverture", "session asiatique")),
         ("croisement", ("croisement", "moyennes croisees")),
         ("retour", ("retour a la moyenne", "bollinger", "retour")),
         ("cassure", ("cassure", "range", "donchian")),
         ("plan", ("plan",)))  # fmt: skip


def strategy_named(text: str) -> str | None:
    """« la cassure de range » → « cassure » ; « cassure » (déjà un nom) aussi."""
    if text in BY_NAME:
        return text
    padded = f" {normalize(text)} "
    for name, words in WORDS:
        if any(f" {w}" in padded for w in words):
            return name
    return None
