"""Une stratégie sur PLUSIEURS marchés à la fois, comme les Turtles : beaucoup de petites
pertes un peu partout, quelques grosses tendances qui paient le reste. Les trades de tous les
marchés réunis en un portefeuille (1 R de risque chacun), jugé avec le même verdict honnête
que sur un seul marché : assez de trades, gain au-delà du hasard, positif sur les deux
moitiés de la période.

Piège évité : choisir après coup « la meilleure stratégie de chaque marché », c'est trouver
celle qui a eu de la chance. Une stratégie jugée sur l'ensemble des marchés est plus sûre."""

from friday.trading.backtest.compare import Result
from friday.trading.backtest.report import Report
from friday.trading.strategies import Strategy

# « Tous les marchés » : les grandes paires et croisées de devises, métaux, pétroles,
# indices, crypto (bougies 1 h sur ~2 ans chez Yahoo pour chacun, vérifié le 17/10/2026)
UNIVERSE = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY",
    "EURGBP", "XAUUSD", "XAGUSD", "USOIL", "UKOIL", "SPX", "NDX", "DAX", "CAC40", "BTCUSD",
    "ETHUSD",
)  # fmt: skip
PORTFOLIO = "portefeuille"


def portfolio(strategy: Strategy, results: list[Result]) -> Result:
    """Les trades de `results` (la même stratégie sur chaque marché) réunis, dans l'ordre où
    ils se ferment : la plus forte baisse est celle qu'on aurait vécue en les tradant tous."""
    trades = sorted((t for r in results for t in r.report.trades),
                    key=lambda t: t.closed or t.opened)  # fmt: skip
    if not trades:
        empty = Report(PORTFOLIO, [])
        return Result(strategy, empty, (empty, empty))
    first = min(t.opened for t in trades)
    middle = first + (max(t.opened for t in trades) - first) / 2
    halves = (Report("1re moitié", [t for t in trades if t.opened < middle]),
              Report("2de moitié", [t for t in trades if t.opened >= middle]))  # fmt: skip
    return Result(strategy, Report(PORTFOLIO, trades), halves)


def by_strategy(markets: list[tuple[object, list[Result]]]) -> dict[str, list[tuple]]:
    """{nom de stratégie : [(marché, résultat)…]} depuis les comparaisons de chaque marché."""
    found: dict[str, list[tuple]] = {}
    for market, results in markets:
        for result in results:
            found.setdefault(result.strategy.name, []).append((market, result))
    return found
