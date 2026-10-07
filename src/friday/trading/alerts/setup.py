"""Le setup du plan se forme-t-il ? Sur la dernière bougie 1 h FERMÉE, exactement les règles
du backtest (engine.setup_ok) : ce qui s'annonce est ce qui a été testé sur l'historique.
Le texte annoncé est construit ici, par le code (le modèle le répète tel quel)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from friday.trading.backtest.engine import open_trade, setup_ok
from friday.trading.backtest.series import atr_series, ema_series, rsi_series
from friday.trading.instruments import Instrument
from friday.trading.market import Candle, _digits
from friday.trading.plan_rules import PlanRules
from friday.trading.sessions import french


@dataclass
class Setup:
    side: str  # « achat » ou « vente »
    bar: Candle  # la bougie 1 h fermée qui le confirme
    line: float | None  # EMA 1 h du repli
    width: float  # ATR 1 h
    rsi_now: float
    rsi_before: float
    stop: float  # indicatif : sous le dernier creux, au moins N ATR (comme le backtest)
    target: float


def closed(hourly: list[Candle], now: datetime) -> list[Candle]:
    """Sans la bougie en cours (Yahoo la renvoie avant sa fermeture)."""
    if hourly and hourly[-1].time + timedelta(hours=1) > now:
        return hourly[:-1]
    return hourly


def detect(hourly: list[Candle], daily: list[Candle], rules: PlanRules) -> Setup | None:
    """Le setup sur la DERNIÈRE bougie de `hourly` (déjà limitée aux bougies fermées)."""
    if len(hourly) < 2:
        return None
    closes = [c.close for c in hourly]
    pull = ema_series(closes, rules.pullback_ema) if rules.pullback_ema else None
    rsi, atr = rsi_series(closes), atr_series(hourly)
    i, bar = len(hourly) - 1, hourly[-1]
    if atr[i] is None or rsi[i] is None or rsi[i - 1] is None:
        return None
    sides = ("achat", "vente")
    if rules.trend_ema:
        finished = [d.close for d in daily if d.time + timedelta(days=1) <= bar.time]
        trend = ema_series(finished, rules.trend_ema)
        if not trend or trend[-1] is None:
            return None
        sides = ("achat",) if bar.close > trend[-1] else ("vente",)
    for side in sides:
        if setup_ok(side, i, bar.close, pull, rsi, atr[i], rules):
            trade = open_trade(side, i, hourly, atr[i], rules)
            return Setup(side, bar, pull[i] if pull else None, atr[i], rsi[i], rsi[i - 1],
                         trade.stop, trade.target)  # fmt: skip
    return None


def announcement(instrument: Instrument, setup: Setup, rules: PlanRules, shift: float) -> str:
    """`shift` : écart Yahoo − graphique (contrat à terme), retiré de tous les niveaux."""
    digits = _digits(instrument)
    p = lambda x: f"{x - shift:,.{digits}f}".replace(",", " ").replace(".", ",")  # noqa: E731
    hour = french(setup.bar.time + timedelta(hours=1), with_day=False)[-5:]
    parts = [f"Alerte setup sur {instrument.name} : {setup.side}"]
    if rules.trend_ema:
        parts[0] += f" dans le sens de l'EMA{rules.trend_ema} journalière"
    parts.append(f"bougie 1 h fermée à {hour} à {p(setup.bar.close)}")
    if setup.line is not None:
        gap = abs(setup.bar.close - setup.line) / setup.width
        parts.append(f"à {gap:.1f} ATR de l'EMA{rules.pullback_ema} 1 h".replace(".", ","))
    way = "remonte" if setup.rsi_now > setup.rsi_before else "baisse"
    parts.append(f"RSI {setup.rsi_now:.0f} qui {way}")
    rr = f"{rules.min_rr or 2:g}".replace(".", ",")
    parts.append(f"stop indicatif {p(setup.stop)}, objectif {rr} R {p(setup.target)}")
    return ", ".join(parts) + ". Vérifie avec la check-list avant d'entrer."
