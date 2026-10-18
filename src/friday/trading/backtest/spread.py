"""Le spread typique d'un marché, retiré de chaque trade (backtest, carnet des setups)."""

from friday.trading.instruments import Instrument

SPREAD_PIPS = {"forex": 1, "metal": 3, "energie": 3, "indice": 1}  # spread typique
SPREAD_SHARE = 0.0005  # crypto, actions : 0,05 % du cours


def spread_of(instrument: Instrument, price: float) -> float:
    pips = SPREAD_PIPS.get(instrument.kind)
    return pips * instrument.pip if pips else price * SPREAD_SHARE
