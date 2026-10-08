"""Le setup de la stratégie choisie (le plan par défaut) se forme-t-il ? Sur la dernière
bougie 1 h FERMÉE, exactement la règle d'entrée du backtest (strategies/) : ce qui s'annonce
est ce qui a été testé sur l'historique. Le texte annoncé est construit ici, par le code."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from friday.trading.instruments import Instrument
from friday.trading.market import Candle, _digits
from friday.trading.plan_rules import PlanRules
from friday.trading.sessions import french
from friday.trading.strategies import Strategy, finished_day
from friday.trading.strategies.plan import PlanStrategy


@dataclass
class Setup:
    side: str  # « achat » ou « vente »
    bar: Candle  # la bougie 1 h fermée qui le confirme
    line: float | None  # EMA 1 h du repli
    width: float  # ATR 1 h
    rsi_now: float
    rsi_before: float
    stop: float  # indicatif : celui de la stratégie, au moins N ATR (comme le backtest)
    target: float
    strategy: Strategy | None = None


def closed(hourly: list[Candle], now: datetime) -> list[Candle]:
    """Sans la bougie en cours (Yahoo la renvoie avant sa fermeture)."""
    if hourly and hourly[-1].time + timedelta(hours=1) > now:
        return hourly[:-1]
    return hourly


def detect(hourly: list[Candle], daily: list[Candle], rules: PlanRules,
           strategy: Strategy | None = None) -> Setup | None:  # fmt: skip
    """Le setup sur la DERNIÈRE bougie de `hourly` (déjà limitée aux bougies fermées)."""
    strategy = strategy or PlanStrategy()
    if len(hourly) < 2:
        return None
    state = strategy.prepare(hourly, daily, rules)
    i, bar = len(hourly) - 1, hourly[-1]
    entry = strategy.entry(state, i, finished_day(daily, bar.time))
    if entry is None or state.rsi[i] is None or state.rsi[i - 1] is None:
        return None
    pull = state.extra.get("pull")
    return Setup(entry.side, bar, pull[i] if pull else None, state.atr[i], state.rsi[i],
                 state.rsi[i - 1], entry.stop, entry.target, strategy)  # fmt: skip


def announcement(instrument: Instrument, setup: Setup, rules: PlanRules, shift: float) -> str:
    """`shift` : écart Yahoo − graphique (contrat à terme), retiré de tous les niveaux."""
    digits = _digits(instrument)
    p = lambda x: f"{x - shift:,.{digits}f}".replace(",", " ").replace(".", ",")  # noqa: E731
    hour = french(setup.bar.time + timedelta(hours=1), with_day=False)[-5:]
    strategy = setup.strategy or PlanStrategy()
    named = "" if strategy.name == "mon_plan" else f" « {strategy.label} »"
    parts = [f"Alerte setup{named} sur {instrument.name} : {setup.side}"]
    if rules.trend_ema and strategy.trend_filter:
        parts[0] += f" dans le sens de l'EMA{rules.trend_ema} journalière"
    parts.append(f"bougie 1 h fermée à {hour} à {p(setup.bar.close)}")
    if setup.line is not None:
        gap = abs(setup.bar.close - setup.line) / setup.width
        parts.append(f"à {gap:.1f} ATR de l'EMA{rules.pullback_ema} 1 h".replace(".", ","))
    way = "remonte" if setup.rsi_now > setup.rsi_before else "baisse"
    parts.append(f"RSI {setup.rsi_now:.0f} qui {way}")
    reward = abs(setup.target - setup.bar.close) / abs(setup.bar.close - setup.stop)
    rr = f"{round(reward, 1):g}".replace(".", ",")
    parts.append(f"stop indicatif {p(setup.stop)}, objectif {rr} R {p(setup.target)}")
    return ", ".join(parts) + ". Vérifie avec la check-list avant d'entrer."
