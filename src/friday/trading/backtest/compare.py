"""La comparaison des stratégies sur un instrument, avec un verdict honnête :

- ✅ « a fonctionné » : au moins FEW trades, gain moyen positif MÊME en retirant sa marge
  d'incertitude, et positif sur CHACUNE des deux moitiés de la période (pas un coup de
  chance concentré sur quelques semaines) ;
- 🟡 « prometteuse » : gain moyen positif, mais pas prouvé (marge, trop peu de trades, ou une
  moitié perdante) ;
- ❌ « n'a pas fonctionné ».

Mêmes données, même moteur, même spread, même gestion du risque pour toutes.
"""

from dataclasses import dataclass

from friday.trading.backtest.engine import simulate
from friday.trading.backtest.report import FEW, Report
from friday.trading.market import Candle
from friday.trading.plan_rules import PlanRules
from friday.trading.strategies import STRATEGIES, Strategy

WORKED, PROMISING, FAILED = "a fonctionné", "prometteuse", "n'a pas fonctionné"
ICONS = {WORKED: "✅", PROMISING: "🟡", FAILED: "❌"}


@dataclass
class Result:
    strategy: Strategy
    report: Report
    halves: tuple[Report, Report]

    @property
    def verdict(self) -> str:
        r = self.report
        if not r.count or (r.expectancy or 0) <= 0:
            return FAILED
        proven = (r.count >= FEW and r.margin is not None and r.expectancy - r.margin > 0
                  and all((h.expectancy or 0) > 0 for h in self.halves))  # fmt: skip
        return WORKED if proven else PROMISING

    def why(self) -> str:
        """Pourquoi « prometteuse » plutôt que « a fonctionné »."""
        r = self.report
        if self.verdict != PROMISING:
            return ""
        if r.count < FEW:
            return f"trop peu de trades ({r.count})"
        if any((h.expectancy or 0) <= 0 for h in self.halves):
            return "perdante sur une moitié de la période"
        return "gain dans la marge du hasard"


def compare(hourly: list[Candle], daily: list[Candle], rules: PlanRules, spread: float = 0.0,
            strategies: tuple[Strategy, ...] = STRATEGIES) -> list[Result]:  # fmt: skip
    """Toutes les stratégies, de la meilleure à la moins bonne (gain moyen par trade)."""
    middle = hourly[len(hourly) // 2].time if hourly else None
    results = []
    for strategy in strategies:
        trades = simulate(hourly, daily, rules, spread, strategy)
        halves = (Report("1re moitié", [t for t in trades if t.opened < middle]),
                  Report("2de moitié", [t for t in trades if t.opened >= middle]))  # fmt: skip
        results.append(Result(strategy, Report(strategy.label, trades), halves))
    order = {WORKED: 0, PROMISING: 1, FAILED: 2}
    return sorted(results, key=lambda x: (order[x.verdict], -(x.report.expectancy or -99)))
