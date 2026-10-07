"""Bilan d'un backtest (en R) et variantes du plan à comparer, chacune ne changeant qu'UNE
règle : on voit ce que chaque règle apporte ou coûte."""

from dataclasses import dataclass, replace

from friday.trading.backtest.engine import Trade
from friday.trading.plan_rules import PlanRules

FEW = 30  # en dessous, l'échantillon est trop petit pour conclure


@dataclass
class Report:
    label: str
    trades: list[Trade]

    @property
    def count(self) -> int:
        return len(self.trades)

    @property
    def results(self) -> list[float]:
        return [t.result_r for t in self.trades if t.result_r is not None]

    @property
    def win_rate(self) -> float | None:
        return sum(r > 0 for r in self.results) / self.count * 100 if self.count else None

    @property
    def expectancy(self) -> float | None:
        """Gain moyen par trade, en R."""
        return sum(self.results) / self.count if self.count else None

    @property
    def margin(self) -> float | None:
        """Marge d'incertitude du gain moyen (± 2 erreurs types) : sous cet écart, deux
        variantes ne se distinguent pas du hasard."""
        if self.count < 2:
            return None
        mean = self.expectancy
        spread = sum((r - mean) ** 2 for r in self.results) / (self.count - 1)
        return 2 * (spread / self.count) ** 0.5

    @property
    def total(self) -> float:
        return sum(self.results)

    @property
    def worst_streak(self) -> int:
        """Plus longue série de pertes d'affilée."""
        worst = run = 0
        for r in self.results:
            run = run + 1 if r <= 0 else 0
            worst = max(worst, run)
        return worst

    @property
    def drawdown(self) -> float:
        """Plus forte baisse du total en R, d'un sommet au creux suivant."""
        peak = total = deepest = 0.0
        for r in self.results:
            total += r
            peak = max(peak, total)
            deepest = max(deepest, peak - total)
        return deepest

    def summary(self) -> str:
        if not self.count:
            return "aucun trade sur la période"
        return (f"{_plural(self.count, 'trade')}, {_n(self.win_rate, 0)} % gagnants, "
                f"{r_text(self.expectancy)} par trade en moyenne (± {_n(self.margin, 2)}), "
                f"total {r_text(self.total)}, "
                f"pire série {_plural(self.worst_streak, 'perte')}, plus forte baisse "
                f"{_n(self.drawdown, 1)} R")  # fmt: skip

    def short(self) -> str:
        """Pour l'oral : l'essentiel seulement."""
        if not self.count:
            return "aucun trade sur la période"
        return (f"{_plural(self.count, 'trade')}, {_n(self.win_rate, 0)} % gagnants, "
                f"{r_text(self.expectancy)} par trade en moyenne, pire série "
                f"{_plural(self.worst_streak, 'perte')}")  # fmt: skip

    def line(self) -> str:
        return f"{self.label} : {self.summary()}"


def variants(rules: PlanRules) -> list[tuple[str, PlanRules]]:
    """Le plan, puis des variantes qui ne changent qu'une règle (celles qui diffèrent)."""
    candidates = [
        ("Sans filtre de tendance", replace(rules, trend_ema=0)),
        ("Sans « RSI qui repart »", replace(rules, rsi_turning=False)),
        ("Repli plus large (2 ATR)", replace(rules, pullback_atr=2.0)),
        ("Stop d'au moins 1 ATR", replace(rules, stop_atr=1.0)),
        ("Stop d'au moins 2 ATR", replace(rules, stop_atr=2.0)),
        ("Objectif 1,5 R", replace(rules, min_rr=1.5)),
        ("Objectif 3 R", replace(rules, min_rr=3.0)),
    ]
    found, seen = [("Ton plan", rules)], {_key(rules)}
    for label, variant in candidates:
        if _key(variant) not in seen:
            found.append((label, variant))
            seen.add(_key(variant))
    return found


def _key(rules: PlanRules) -> tuple:
    return (rules.trend_ema, rules.pullback_ema, rules.pullback_atr, rules.rsi_low,
            rules.rsi_high, rules.rsi_turning, rules.stop_atr, rules.min_rr or 2.0)  # fmt: skip


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'s' if count > 1 else ''}"


def _n(value: float | None, digits: int) -> str:
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def r_text(value: float | None) -> str:
    if value is None:
        return "—"
    value = round(value, 2) + 0.0  # pas de « -0,00 »
    return (f"{value:+.2f} R" if value else "0,00 R").replace(".", ",")
