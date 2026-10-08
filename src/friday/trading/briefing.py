"""Le briefing trading du début de journée : annonces fortes du jour, mouvement de la nuit,
niveaux clés, tendance (et donc le sens que le plan autorise), rappel des règles du plan.
Tout est calculé ici, par le code ; Friday le lit tel quel (les chiffres ne passent pas par
le modèle, qui les mélangeait). Rien de personnel ne part en ligne : seuls des cours publics
sont lus (Yahoo, ForexFactory)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from friday.trading.backtest.series import ema_series
from friday.trading.calendar import PARIS, Event, delay
from friday.trading.calendar_fr import french
from friday.trading.instruments import Instrument
from friday.trading.market import Candle, MarketUnavailable, _digits, pivots
from friday.trading.plan_rules import PlanRules
from friday.trading.sessions import DAYS

History = Callable[[Instrument], tuple[list[Candle], list[Candle]]]  # (1 h, journalier)


@dataclass
class TradingBriefing:
    parts: list[tuple[str, str]] = field(default_factory=list)  # (titre, texte)

    def text(self) -> str:
        return "\n".join(text for _, text in self.parts)


def build(instruments: list[Instrument], history: History, events: list[Event] | None,
          rules: PlanRules, now: datetime, hours: tuple[int, int] = (9, 18),
          offsets: dict[str, float] | None = None, open_trades: int = 0,
          alerts: int = 0, strategy_of=None) -> TradingBriefing:  # fmt: skip
    """`strategy_of(symbole)` : la stratégie choisie pour l'instrument (le plan sinon)."""
    local = now.astimezone(PARIS)
    title = f"Briefing trading du {DAYS[local.weekday()]} {local:%d/%m}."
    briefing = TradingBriefing([("Briefing trading", title)])
    currencies = {c for i in instruments for c in i.currencies}
    briefing.parts.append(("Annonces fortes du jour", _events(events, currencies, now)))
    since = _yesterday_close(now, hours[1])
    for instrument in instruments:
        try:
            hourly, daily = history(instrument)
            shift = (offsets or {}).get(instrument.symbol, 0.0)
            strategy = strategy_of(instrument.symbol) if strategy_of else None
            text = _instrument(instrument, hourly, daily, rules, now, since, shift, strategy)
        except MarketUnavailable:
            text = f"{_name(instrument)} : cours indisponibles ce matin."
        briefing.parts.append((instrument.name, text))
    briefing.parts.append(("Ton plan", _plan(rules, open_trades, alerts)))
    return briefing


def _events(events: list[Event] | None, currencies: set[str], now: datetime) -> str:
    if events is None:
        return "Calendrier économique indisponible : vérifie les annonces avant d'entrer."
    today = now.astimezone(PARIS).date()
    strong = sorted((e for e in events if e.impact == "High"
                     and (e.currency in currencies or e.currency == "All")
                     and e.time.astimezone(PARIS).date() == today),
                    key=lambda e: e.time)  # fmt: skip
    if not strong:
        return "Aucune annonce forte aujourd'hui sur tes devises."
    said = []
    for e in strong:
        minutes = (e.time - now).total_seconds() / 60
        when = f"dans {delay(minutes)}" if minutes > 0 else "déjà publiée"
        said.append(f"{e.time.astimezone(PARIS):%H:%M}".replace(":", " h ") + f", {e.currency}, "
                    f"{french(e.title)} ({when})")  # fmt: skip
    return "Annonces fortes du jour : " + " ; ".join(said) + "."


def _yesterday_close(now: datetime, end_hour: int) -> datetime:
    """La fin de la dernière journée de trading avant aujourd'hui (le vendredi, le lundi)."""
    day = now.astimezone(PARIS).replace(hour=end_hour, minute=0, second=0, microsecond=0)
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _instrument(i: Instrument, hourly: list[Candle], daily: list[Candle], rules: PlanRules,
                now: datetime, since: datetime, shift: float, strategy=None) -> str:  # fmt: skip
    digits = _digits(i)
    p = lambda x: f"{x - shift:,.{digits}f}".replace(",", " ").replace(".", ",")  # noqa: E731
    price = hourly[-1].close
    parts = [f"{_name(i)} : {p(price)}"]
    before = [c for c in hourly if c.time + timedelta(hours=1) <= since]
    night = [c for c in hourly if c.time + timedelta(hours=1) > since]
    if before and night:
        change = round((price - before[-1].close) / before[-1].close * 100, 2) + 0.0  # ni « -0,00 »
        parts[0] += (f", {change:+.2f} %".replace(".", ",") + f" depuis hier {since:%H} h "
                     f"(nuit entre {p(min(c.low for c in night))} et "
                     f"{p(max(c.high for c in night))})")  # fmt: skip
    mine = strategy is not None and strategy.name != "plan"
    if mine:
        parts.append(f"Ta stratégie : {strategy.label} ({strategy.summary})")
    who = "ta stratégie" if mine else "ton plan"
    follows = strategy is None or strategy.trend_filter
    finished = [d for d in daily if d.time + timedelta(days=1) <= now]  # tendance : séances finies
    if rules.trend_ema and finished:
        line = ema_series([d.close for d in finished], rules.trend_ema)[-1]
        if line is not None:
            up = price > line
            allowed = (f", {who} n'autorise que des {'achats' if up else 'ventes'} aujourd'hui"
                       if follows else "")  # fmt: skip
            parts.append(f"Tendance {'haussière' if up else 'baissière'} : "
                         f"{'au-dessus' if up else 'en dessous'} de l'EMA{rules.trend_ema} "
                         f"journalière ({p(line)}){allowed}")  # fmt: skip
    levels = []
    if (y := _previous_day(hourly, since)) is not None:
        pv = pivots(y)
        levels.append(f"plus haut d'hier {p(y.high)}, plus bas {p(y.low)}")
        levels.append(f"pivot {p(pv['P'])}, R1 {p(pv['R1'])}, S1 {p(pv['S1'])}")
    if rules.pullback_ema:
        closed = [c.close for c in hourly if c.time + timedelta(hours=1) <= now]
        line = ema_series(closed, rules.pullback_ema)[-1] if closed else None
        if line is not None:
            levels.append(f"EMA{rules.pullback_ema} 1 h {p(line)}")
    if levels:
        parts.append("Niveaux clés : " + " ; ".join(levels))
    return ". ".join(parts) + "."


def _previous_day(hourly: list[Candle], since: datetime) -> Candle | None:
    """« Hier » : la dernière journée de trading (minuit à minuit, heure de Paris), rebâtie
    avec les bougies 1 h. La bougie journalière de Yahoo ne convient pas : la dernière est la
    séance en cours, datée différemment selon le marché (l'avant-veille passait pour hier)."""
    day = since.date()
    candles = [c for c in hourly if c.time.astimezone(PARIS).date() == day]
    if not candles:
        return None
    return Candle(candles[0].time, candles[0].open, max(c.high for c in candles),
                  min(c.low for c in candles), candles[-1].close)  # fmt: skip


def _name(i: Instrument) -> str:
    return i.name[0].upper() + i.name[1:]


def _g(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _plan(rules: PlanRules, open_trades: int, alerts: int) -> str:
    said = []
    if rules.pullback_ema:
        said.append(f"entrée près de l'EMA{rules.pullback_ema} 1 h")
    said.append(f"RSI entre {_g(rules.rsi_low)} et {_g(rules.rsi_high)}"
                + (" qui repart" if rules.rsi_turning else "") + " à l'achat")  # fmt: skip
    if rules.stop_atr:
        said.append(f"stop d'au moins {_g(rules.stop_atr)} ATR")
    if rules.min_rr:
        said.append(f"objectif d'au moins {_g(rules.min_rr)} R")
    if rules.max_risk:
        said.append(f"risque d'au plus {_g(rules.max_risk)} %")
    if rules.news_minutes:
        said.append(f"pas d'entrée {rules.news_minutes} min avant une annonce forte")
    plural = lambda n, word: f"{n} {word}{'s' if n > 1 else ''}"  # noqa: E731
    state = f"{plural(open_trades, 'trade')} ouvert{'s' if open_trades > 1 else ''} au journal"
    if alerts:
        state += f", {plural(alerts, 'alerte')} en cours"
    return f"Ton plan : {', '.join(said)}. {state[0].upper()}{state[1:]}."
