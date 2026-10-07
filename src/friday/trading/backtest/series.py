"""Indicateurs en SÉRIE (une valeur par bougie, None tant qu'il n'y a pas assez d'historique),
calculés en un seul passage : le backtest les lit bougie après bougie sans recalcul.

Mêmes définitions que market.py (EMA amorcée par la moyenne simple, RSI et ATR de Wilder) :
la dernière valeur d'une série égale le calcul « instantané » de la check-list (testé).
"""

from friday.trading.market import Candle

Series = list[float | None]


def ema_series(values: list[float], period: int) -> Series:
    out: Series = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    value, k = sum(values[:period]) / period, 2 / (period + 1)
    out[period - 1] = value
    for i in range(period, len(values)):
        value += k * (values[i] - value)
        out[i] = value
    return out


def rsi_series(closes: list[float], period: int = 14) -> Series:
    out: Series = [None] * len(closes)
    if len(closes) <= period:
        return out
    changes = [b - a for a, b in zip(closes, closes[1:], strict=False)]
    gains = sum(max(c, 0) for c in changes[:period]) / period
    losses = sum(max(-c, 0) for c in changes[:period]) / period
    out[period] = _rsi(gains, losses)
    for i in range(period, len(changes)):
        gains = (gains * (period - 1) + max(changes[i], 0)) / period
        losses = (losses * (period - 1) + max(-changes[i], 0)) / period
        out[i + 1] = _rsi(gains, losses)
    return out


def atr_series(candles: list[Candle], period: int = 14) -> Series:
    out: Series = [None] * len(candles)
    if len(candles) <= period:
        return out
    ranges = [
        max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        for p, c in zip(candles, candles[1:], strict=False)
    ]
    value = sum(ranges[:period]) / period
    out[period] = value
    for i in range(period, len(ranges)):
        value = (value * (period - 1) + ranges[i]) / period
        out[i + 1] = value
    return out


def _rsi(gains: float, losses: float) -> float:
    return 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)
