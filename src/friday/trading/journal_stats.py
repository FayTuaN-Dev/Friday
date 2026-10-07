"""Ce que le journal apprend : les trades clôturés regroupés par setup, instrument, heure,
jour, plan respecté ou non, état d'esprit — et les leçons qui en ressortent, calculées par le
code. Tout est en R : aucun montant, aucun prix, aucune raison écrite (bilan ANONYME, seul
joignable à une revue par Claude, via l'aperçu)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from friday.trading.journal import Trade

MIN_GROUP = 3  # en dessous, un groupe ne permet aucune leçon
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOODS = ("calme", "confiant", "impatient", "stressé", "fatigué", "revanche après une perte",
         "euphorique après un gain")  # fmt: skip


@dataclass
class Group:
    name: str
    results: list[float]

    @property
    def count(self) -> int:
        return len(self.results)

    @property
    def average(self) -> float:
        return sum(self.results) / self.count

    @property
    def win_rate(self) -> float:
        return sum(r > 0 for r in self.results) / self.count * 100

    def line(self) -> str:
        return (f"{self.name} : {self.count} trade{'s' if self.count > 1 else ''}, "
                f"{self.win_rate:.0f} % gagnants, {r(self.average)} en moyenne, total "
                f"{r(sum(self.results))}")  # fmt: skip


def r(value: float) -> str:
    value = round(value, 2) + 0.0
    return (f"{value:+.2f} R" if value else "0,00 R").replace(".", ",")


def _hour(trade: Trade) -> str:
    hour = datetime.fromisoformat(trade.opened_at).hour
    for end, label in ((9, "avant 9 h"), (12, "9 h – 12 h"), (15, "12 h – 15 h"),
                       (18, "15 h – 18 h")):  # fmt: skip
        if hour < end:
            return label
    return "après 18 h"


def _plan(trade: Trade) -> str:
    return {True: "plan respecté", False: "plan NON respecté"}.get(trade.plan_ok, "")


KEYS: dict[str, Callable[[Trade], str]] = {
    "setup": lambda t: t.setup,
    "instrument": lambda t: t.pair,
    "heure d'entrée": _hour,
    "jour": lambda t: DAYS[datetime.fromisoformat(t.opened_at).weekday()],
    "plan": _plan,
    "état d'esprit": lambda t: t.mood,
}


def groups(trades: list[Trade], key: Callable[[Trade], str]) -> list[Group]:
    """Groupes des trades clôturés (sans les non renseignés), les plus fournis d'abord ; la
    casse est ignorée (« repli EMA50 » = « Repli EMA50 »)."""
    found: dict[str, Group] = {}
    for t in sorted(trades, key=lambda t: t.id):  # le nom : la première écriture utilisée
        name = key(t)
        if t.result_r is None or not name:
            continue
        found.setdefault(name.casefold(), Group(name, [])).results.append(t.result_r)
    return sorted(found.values(), key=lambda g: (-g.count, -g.average))


def lessons(trades: list[Trade]) -> list[str]:
    """Les constats chiffrés (groupes d'au moins MIN_GROUP trades seulement)."""
    found = []
    plan = {g.name: g for g in groups(trades, _plan) if g.count >= MIN_GROUP}
    if len(plan) == 2:
        ok, ko = plan["plan respecté"], plan["plan NON respecté"]
        found.append(f"Plan respecté : {r(ok.average)} en moyenne ; plan non respecté : "
                     f"{r(ko.average)} ({ko.count} trades).")  # fmt: skip
    for title, key in KEYS.items():
        if title == "plan":
            continue
        enough = [g for g in groups(trades, key) if g.count >= MIN_GROUP]
        if len(enough) >= 2:
            best, worst = max(enough, key=lambda g: g.average), min(enough, key=lambda g: g.average)
            found.append(f"{title.capitalize()} : le meilleur est « {best.name} » "
                         f"({r(best.average)}), le pire « {worst.name} » "
                         f"({r(worst.average)}).")  # fmt: skip
    costly = [g for g in groups(trades, KEYS["setup"]) if g.count >= MIN_GROUP and g.average < 0]
    for g in costly:
        found.append(f"Le setup « {g.name} » perd en moyenne ({r(g.average)} sur {g.count} "
                     "trades) : à revoir, ou à abandonner.")  # fmt: skip
    return found


def breakdown(trades: list[Trade]) -> str:
    lines = []
    for title, key in KEYS.items():
        found = groups(trades, key)
        if found:
            lines.append(f"Par {title} :")
            lines += [f"- {g.line()}" for g in found]
    return "\n".join(lines) or "Aucun trade clôturé à analyser."


def week(trades: list[Trade], now: datetime) -> list[Trade]:
    """Les trades clôturés ces 7 derniers jours."""
    start = now - timedelta(days=7)
    return [t for t in trades if t.closed_at and datetime.fromisoformat(t.closed_at) >= start]


def review_text(trades: list[Trade], summary: str, now: datetime) -> str:
    """Le bilan anonyme pour la revue hebdomadaire (aucun prix, montant ni raison écrite)."""
    recent = week(trades, now)
    lines = [f"Bilan global : {summary}", f"Cette semaine : {len(recent)} trade(s) clôturé(s)."]
    for t in sorted(recent, key=lambda t: t.closed_at):
        details = [x for x in (t.setup and f"setup « {t.setup} »", _plan(t),
                               t.mood and f"état d'esprit : {t.mood}") if x]  # fmt: skip
        day = KEYS["jour"](t)
        lines.append(f"- {t.direction} {t.pair}, ouvert {day} ({_hour(t)}) : {r(t.result_r)}"
                     + (f" ; {', '.join(details)}" if details else ""))  # fmt: skip
    lines += ["Statistiques de tout le journal :", breakdown(trades)]
    if found := lessons(trades):
        lines += ["Constats calculés sur le PC :"] + [f"- {x}" for x in found]
    return "\n".join(lines)
