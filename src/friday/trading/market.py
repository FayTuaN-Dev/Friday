"""Données de marché : bougies OHLC (Yahoo Finance, gratuit, sans clé) et indicateurs calculés
SUR LE PC (moyennes mobiles, RSI, ATR, plus hauts / bas, pivots). Le modèle ne calcule rien.

Yahoo est une source non officielle : si elle ne répond pas, `MarketUnavailable` (l'analyse
part sans ces données, et l'aperçu le dit).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from friday.trading.instruments import Instrument

log = logging.getLogger(__name__)

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 10


class MarketUnavailable(Exception):
    """Message destiné à l'utilisateur."""


@dataclass
class Candle:
    time: datetime  # ouverture, en UTC
    open: float
    high: float
    low: float
    close: float


@dataclass
class Quote:
    price: float
    previous_close: float | None
    currency: str
    time: datetime

    @property
    def change_percent(self) -> float | None:
        if not self.previous_close:
            return None
        return (self.price - self.previous_close) / self.previous_close * 100


def fetch(ticker: str, interval: str, period: str, get=httpx.get) -> tuple[Quote, list[Candle]]:
    """Cours actuel et bougies (`interval` : 1h, 1d… ; `period` : 5d, 1mo, 1y…)."""
    try:
        response = get(URL.format(ticker=ticker), params={"interval": interval, "range": period},
                       headers=HEADERS, timeout=TIMEOUT)  # fmt: skip
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise MarketUnavailable(f"Cours de {ticker} indisponibles ({error}).") from error
    meta = result.get("meta", {})
    prices = (result.get("indicators", {}).get("quote") or [{}])[0]
    candles = [
        Candle(datetime.fromtimestamp(t, UTC), o, h, low, c)
        for t, o, h, low, c in zip(result.get("timestamp") or [], prices.get("open", []),
                                   prices.get("high", []), prices.get("low", []),
                                   prices.get("close", []), strict=False)
        if None not in (o, h, low, c)
    ]  # fmt: skip
    if not candles or meta.get("regularMarketPrice") is None:
        raise MarketUnavailable(f"Aucun cours pour {ticker}.")
    quote = Quote(
        meta["regularMarketPrice"], meta.get("chartPreviousClose") or meta.get("previousClose"),
        meta.get("currency", ""), datetime.fromtimestamp(meta.get("regularMarketTime", 0), UTC),
    )  # fmt: skip
    return quote, candles


def regroup(candles: list[Candle], hours: int) -> list[Candle]:
    """Bougies de 1 h regroupées par `hours` heures (4 h), alignées sur minuit UTC."""
    groups: dict[datetime, list[Candle]] = {}
    for candle in candles:
        start = candle.time.replace(hour=candle.time.hour - candle.time.hour % hours, minute=0,
                                    second=0, microsecond=0)  # fmt: skip
        groups.setdefault(start, []).append(candle)
    return [
        Candle(
            start,
            group[0].open,
            max(c.high for c in group),
            min(c.low for c in group),
            group[-1].close,
        )  # fmt: skip
        for start, group in sorted(groups.items())
    ]


# --- indicateurs (déterministes) ------------------------------------------------------------


def sma(values: list[float], period: int) -> float | None:
    return sum(values[-period:]) / period if len(values) >= period else None


def ema(values: list[float], period: int) -> float | None:
    """Moyenne mobile exponentielle, amorcée par la moyenne simple des `period` premières."""
    if len(values) < period:
        return None
    value, k = sum(values[:period]) / period, 2 / (period + 1)
    for v in values[period:]:
        value += k * (v - value)
    return value


def rsi(closes: list[float], period: int = 14) -> float | None:
    """RSI de Wilder."""
    if len(closes) <= period:
        return None
    changes = [b - a for a, b in zip(closes, closes[1:], strict=False)]
    gains = sum(max(c, 0) for c in changes[:period]) / period
    losses = sum(max(-c, 0) for c in changes[:period]) / period
    for change in changes[period:]:
        gains = (gains * (period - 1) + max(change, 0)) / period
        losses = (losses * (period - 1) + max(-change, 0)) / period
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def atr(candles: list[Candle], period: int = 14) -> float | None:
    """Average True Range (volatilité moyenne d'une bougie), lissage de Wilder."""
    if len(candles) <= period:
        return None
    ranges = [
        max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        for p, c in zip(candles, candles[1:], strict=False)
    ]
    value = sum(ranges[:period]) / period
    for r in ranges[period:]:
        value = (value * (period - 1) + r) / period
    return value


def pivots(day: Candle) -> dict[str, float]:
    """Points pivots classiques, à partir de la veille."""
    p = (day.high + day.low + day.close) / 3
    return {"S2": p - (day.high - day.low), "S1": 2 * p - day.high, "P": p,
            "R1": 2 * p - day.low, "R2": p + (day.high - day.low)}  # fmt: skip


@dataclass
class Snapshot:
    instrument: Instrument
    quote: Quote
    hourly: list[Candle]
    daily: list[Candle]

    def text(self, recent: int = 12, chart: float | None = None) -> str:
        """Résumé compact pour Claude (et l'aperçu). `chart` : le cours affiché sur le graphique
        TradingView de l'utilisateur ; s'il diffère (contrat à terme contre comptant : ~28 points
        sur l'or, constaté), les niveaux sont recalés sur lui."""
        i, q = self.instrument, self.quote
        digits = _digits(i)
        shift = q.price - chart if chart and i.note else 0.0  # seulement pour un contrat à terme
        f = lambda x: "—" if x is None else f"{x - shift:.{digits}f}"  # noqa: E731
        width = lambda x: "—" if x is None else f"{x:.{digits}f}"  # noqa: E731 (écart : non décalé)
        closes_d = [c.close for c in self.daily]
        four = regroup(self.hourly, 4)
        lines = [
            f"Instrument : {i.label}, symbole Yahoo {i.yahoo}"
            + (f" ({i.note})" if i.note else "")
            + f", devise {q.currency or i.quote}.",
            f"Dernier cours : {f(q.price)} ({_pct(q.change_percent)} depuis la clôture d'hier), "
            f"à {q.time:%d/%m %H:%M} UTC.",
        ]
        if chart:
            lines.append(f"Cours affiché sur le graphique TradingView de l'utilisateur : "
                         f"{chart:.{digits}f}.")  # fmt: skip
        if shift:
            lines.append(
                f"Écart contrat à terme / comptant : {shift:+.{digits}f}. TOUS les niveaux "
                "ci-dessous (cours, moyennes, plus hauts/bas, pivots, bougies) sont recalés sur "
                "le cours du graphique ; RSI et ATR ne changent pas."
            )
        lines += [
            f"Journalier : MM20 {f(sma(closes_d, 20))}, MM50 {f(sma(closes_d, 50))}, MM200 "
            f"{f(sma(closes_d, 200))}, RSI14 {_n(rsi(closes_d))}, ATR14 {width(atr(self.daily))}.",
            f"4 h : RSI14 {_n(rsi([c.close for c in four]))}, ATR14 {width(atr(four))}. "
            f"1 h : RSI14 {_n(rsi([c.close for c in self.hourly]))}, "
            f"ATR14 {width(atr(self.hourly))}.",
        ]
        if len(self.daily) >= 21:
            month = self.daily[-21:-1]
            lines.append(f"Plus haut / plus bas sur 20 jours : {f(max(c.high for c in month))}"
                         f" / {f(min(c.low for c in month))}.")  # fmt: skip
        if len(self.daily) >= 2:
            levels = pivots(self.daily[-2])
            lines.append("Pivots du jour : " + ", ".join(f"{k} {f(v)}" for k, v in levels.items())
                         + ".")  # fmt: skip
        lines.append("Dernières bougies 4 h (UTC, ouverture/haut/bas/clôture) :")
        for c in four[-recent:]:
            lines.append(f"{c.time:%d/%m %Hh} {f(c.open)} {f(c.high)} {f(c.low)} {f(c.close)}")
        return "\n".join(lines)


def _digits(instrument: Instrument) -> int:
    """Décimales affichées : une de plus que le pip en forex (les « pipettes »)."""
    text = f"{instrument.pip:.10f}".rstrip("0")
    decimals = len(text.split(".")[1]) if "." in text else 0
    return decimals + 1 if instrument.kind == "forex" else max(2, decimals)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f} %"


def _n(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}"


def snapshot(instrument: Instrument, get=httpx.get) -> Snapshot:
    """Cours, bougies de 1 h (1 mois) et journalières (1 an)."""
    quote, hourly = fetch(instrument.yahoo, "1h", "1mo", get)
    _, daily = fetch(instrument.yahoo, "1d", "1y", get)
    # La « clôture précédente » de Yahoo est celle d'avant la période demandée (un mois) :
    # la variation du jour se calcule sur la clôture d'hier.
    if len(daily) >= 2:
        quote.previous_close = daily[-2].close
    return Snapshot(instrument, quote, hourly, daily)
