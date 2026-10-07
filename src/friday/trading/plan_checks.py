"""Les règles du plan vérifiées une par une (voir checklist.py). Chaque fonction rend un
`Check`, ou None si la règle est désactivée (réglée à 0)."""

import re
from dataclasses import replace
from datetime import datetime

from friday.trading.calendar import PARIS, Event, delay
from friday.trading.checklist import KO, OK, UNKNOWN, Check, Context, Idea, Market, Verdict
from friday.trading.instruments import Instrument
from friday.trading.market import _digits, atr, ema, rsi
from friday.trading.plan_rules import PlanRules
from friday.trading.sessions import french


def evaluate(idea: Idea, market: Market | None, context: Context, rules: PlanRules) -> Verdict:
    idea.check_sides()
    p = _formatter(idea.instrument)
    if market is None:
        found = [Check("Données de marché", UNKNOWN, "cours indisponibles : tendance, RSI, EMA "
                       "et ATR non vérifiés")]  # fmt: skip
    else:
        found = [_trend(idea, market, rules, p), _pullback(idea, market, rules, p),
                 _rsi(idea, market, rules), _stop(idea, market, rules, p)]  # fmt: skip
    found += [_reward(idea, rules, p), _risk(idea, context, rules), _news(idea, context, rules),
              _open(context, rules)]  # fmt: skip
    # Virgule décimale française partout (« 0,05 lot », « 1,5 ATR »)
    comma = lambda text: re.sub(r"(?<=\d)\.(?=\d)", ",", text)  # noqa: E731
    return Verdict([replace(c, rule=comma(c.rule), detail=comma(c.detail)) for c in found if c])


# --- règles -----------------------------------------------------------------------------------


def _trend(idea: Idea, m: Market, rules: PlanRules, p) -> Check | None:
    if not rules.trend_ema:
        return None
    name = f"Tendance (EMA{rules.trend_ema} journalière)"
    line = ema([c.close for c in m.daily], rules.trend_ema)
    if line is None:
        return Check(name, UNKNOWN, "pas assez d'historique")
    above = m.price > line
    side = "au-dessus" if above else "en dessous"
    where = f"cours {p(m.price - m.shift)} {side} de l'EMA ({p(line - m.shift)})"
    if above == idea.buy:
        return Check(name, OK, f"{where} : {idea.direction} dans le sens de la tendance")
    return Check(name, KO, f"{where} : {idea.direction} à contre-tendance")


def _pullback(idea: Idea, m: Market, rules: PlanRules, p) -> Check | None:
    if not rules.pullback_ema:
        return None
    name = f"Repli sur l'EMA{rules.pullback_ema} 1 h"
    line, width = ema([c.close for c in m.hourly], rules.pullback_ema), atr(m.hourly)
    if line is None or not width:
        return Check(name, UNKNOWN, "pas assez d'historique")
    line -= m.shift
    # Contrat à terme sans graphique visible : l'entrée ne se compare pas, le cours actuel si
    reference, what = (idea.entry, "entrée") if m.shift_known else (m.price, "cours actuel")
    gap = abs(reference - line) / width
    detail = f"{what} à {gap:.2f} ATR de l'EMA ({p(line)}) ; maximum {rules.pullback_atr:g} ATR" + (
        "" if m.shift_known else " (graphique non visible : niveaux du contrat à terme)"
    )
    return Check(name, OK if gap <= rules.pullback_atr else KO, detail)


def _rsi(idea: Idea, m: Market, rules: PlanRules) -> Check:
    low, high = (rules.rsi_low, rules.rsi_high) if idea.buy else (100 - rules.rsi_high,
                                                                   100 - rules.rsi_low)  # fmt: skip
    name = f"RSI 14 (1 h) entre {low:g} et {high:g}"
    closes = [c.close for c in m.hourly]
    now, before = rsi(closes), rsi(closes[:-1])
    if now is None or before is None:
        return Check(name, UNKNOWN, "pas assez d'historique")
    inside = low <= now <= high
    turning = now > before if idea.buy else now < before
    way = "remonte" if now > before else "baisse"
    detail = f"RSI {now:.1f} (avant : {before:.1f}, il {way})"
    if not inside:
        return Check(name, KO, detail + " : hors de la zone")
    if rules.rsi_turning and not turning:
        return Check(name, KO, detail + f" : il doit {'remonter' if idea.buy else 'baisser'}")
    return Check(name, OK, detail)


def _stop(idea: Idea, m: Market, rules: PlanRules, p) -> Check | None:
    if not rules.stop_atr:
        return None
    name = f"Stop d'au moins {rules.stop_atr:g} ATR (1 h)"
    width = atr(m.hourly)
    if not width:
        return Check(name, UNKNOWN, "pas assez d'historique")
    distance = abs(idea.entry - idea.stop)
    detail = (f"stop à {p(distance)} = {distance / width:.2f} ATR (ATR 1 h : {p(width)} ; "
              f"minimum {p(rules.stop_atr * width)})")  # fmt: skip
    return Check(name, OK if distance >= rules.stop_atr * width else KO, detail)


def _reward(idea: Idea, rules: PlanRules, p) -> Check | None:
    if not rules.min_rr:
        return None
    name = f"Objectif d'au moins {rules.min_rr:g} R"
    risk = abs(idea.entry - idea.stop)
    needed = idea.entry + (1 if idea.buy else -1) * rules.min_rr * risk
    if idea.target is None:
        return Check(name, UNKNOWN, f"pas d'objectif donné ; à {rules.min_rr:g} R il serait à "
                                    f"{p(needed)}")  # fmt: skip
    ratio = abs(idea.target - idea.entry) / risk
    detail = f"objectif {p(idea.target)} = {ratio:.1f} R"
    if ratio + 1e-9 >= rules.min_rr:
        return Check(name, OK, detail)
    return Check(name, KO, detail + f" (il faudrait au moins {p(needed)})")


def _risk(idea: Idea, c: Context, rules: PlanRules) -> Check | None:
    if not rules.max_risk:
        return None
    name = f"Risque d'au plus {rules.max_risk:g} %"
    if idea.risk_percent is not None:
        ok = idea.risk_percent <= rules.max_risk + 1e-9
        return Check(name, OK if ok else KO, f"tu risques {idea.risk_percent:g} %")
    if not rules.capital or not c.value_per_lot:
        why = "capital inconnu (Réglages → Trading)" if not rules.capital else "valeur du pip"
        return Check(name, UNKNOWN, f"{why} : dis le risque en %, ou la taille et le capital")
    loss_per_lot = abs(idea.entry - idea.stop) / idea.instrument.pip * c.value_per_lot
    allowed = rules.capital * rules.max_risk / 100
    largest = int(allowed / loss_per_lot * 100 + 1e-9) / 100
    unit = "titre(s)" if idea.instrument.kind == "action" else "lot(s)"
    if idea.lots is None:
        return Check(name, OK if largest > 0 else KO,
                     f"à condition de prendre au plus {largest:g} {unit} "
                     f"({allowed:.0f} {c.account} de perte au stop)")  # fmt: skip
    percent = idea.lots * loss_per_lot / rules.capital * 100
    detail = f"{idea.lots:g} {unit} = {percent:.2f} % du capital (au plus {largest:g} {unit})"
    return Check(name, OK if percent <= rules.max_risk + 1e-9 else KO, detail)


def _news(idea: Idea, c: Context, rules: PlanRules) -> Check | None:
    if not rules.news_minutes:
        return None
    name = f"Pas d'annonce forte dans les {rules.news_minutes} min"
    if c.events is None:
        return Check(name, UNKNOWN, "calendrier économique indisponible")
    strong = sorted(
        (e for e in c.events
         if e.impact == "High" and (e.currency in idea.instrument.currencies or e.currency == "All")
         and e.time > c.now),
        key=lambda e: e.time,
    )  # fmt: skip
    soon = [e for e in strong if (e.time - c.now).total_seconds() <= rules.news_minutes * 60]
    if soon:
        return Check(name, KO, "; ".join(_event(e, c.now) for e in soon))
    today = c.now.astimezone(PARIS).date()
    later = [e for e in strong if e.time.astimezone(PARIS).date() == today]
    return Check(name, OK, f"prochaine aujourd'hui : {_event(later[0], c.now)}" if later
                 else "aucune annonce forte d'ici la fin de la journée")  # fmt: skip


def _open(c: Context, rules: PlanRules) -> Check | None:
    if not rules.max_open or c.open_trades is None:
        return None
    name = f"Au plus {rules.max_open} trade(s) ouvert(s)"
    detail = f"{c.open_trades} déjà ouvert(s) au journal"
    return Check(name, OK if c.open_trades < rules.max_open else KO, detail)


def _event(e: Event, now: datetime) -> str:
    minutes = (e.time - now).total_seconds() / 60
    return f"{e.currency} {e.title} à {french(e.time, with_day=False)[-5:]} (dans {delay(minutes)})"


def _formatter(instrument: Instrument):
    digits = _digits(instrument)
    return lambda x: f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")
