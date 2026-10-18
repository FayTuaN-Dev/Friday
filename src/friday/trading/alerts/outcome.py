"""Ce qu'un setup du carnet aurait donné, s'il avait été pris : rejoué sur les bougies qui
ont suivi, avec EXACTEMENT les sorties du backtest (stop, objectif, sortie suiveuse, spread).
C'est ce qui permet de juger, après coup, les setups pris et ceux que Claude a refusés."""

from datetime import datetime

from friday.trading.backtest.engine import Trade, _exit, _trail_level
from friday.trading.market import Candle


def follow(entry: dict, bars: list[Candle], spread: float) -> tuple[str, float] | None:
    """(fermé le, résultat en R) si le trade est terminé sur `bars` ; None s'il court encore
    (ou si les bougies ne vont pas au-delà de celle du setup)."""
    start = datetime.fromisoformat(entry["bar"])
    first = next((i for i, bar in enumerate(bars) if bar.time > start), None)
    if first is None:
        return None
    trade = Trade(start, entry["side"], entry["close"], entry["stop"], entry["target"],
                  entry["trail"])  # fmt: skip
    channels: dict = {}
    for i in range(first, len(bars)):
        if _exit(trade, bars[i], spread, _trail_level(trade, bars, i, channels)):
            return trade.closed.isoformat(), trade.result_r
    return None
