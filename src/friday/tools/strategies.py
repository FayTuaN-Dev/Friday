"""Outils du mode trading : la bibliothèque de stratégies (T7). « Compare les stratégies sur
l'or » : chacune backtestée (même moteur, même spread, même risque) avec un verdict honnête ;
« choisis la cassure de range pour l'or » : elle devient celle des alertes, de la check-list
et du briefing (une stratégie qui n'a pas fonctionné est refusée). Tout sur le PC."""

import time
from concurrent.futures import ThreadPoolExecutor

from friday.tools.backtest import load_history, spread_of
from friday.tools.base import Display, Tool, ToolResult
from friday.tools.strategies_markets import all_strategies, asked_strategy, one_strategy
from friday.trading import risk_calc
from friday.trading.backtest.compare import FAILED, ICONS, PROMISING, WORKED, Result, compare
from friday.trading.backtest.portfolio import UNIVERSE
from friday.trading.backtest.report import r_text
from friday.trading.instruments import Instrument, by_symbol
from friday.trading.plan_book import PREFIX
from friday.trading.plan_rules import load_rules
from friday.trading.strategies import BY_NAME, STRATEGIES, strategy_named

KEEP_SECONDS = 3600
LOADERS = 4  # marchés lus en même temps chez Yahoo (20 marchés : ~3 s, mesuré)


class StrategyLab:
    """L'historique et les comparaisons, gardés une heure (une comparaison : ~1 s)."""

    def __init__(self, trading, history=load_history) -> None:
        self.trading, self.history = trading, history
        self._results: dict[tuple, tuple[float, str, list[Result]]] = {}

    def results(self, instrument: Instrument, only: str | None = None) -> tuple[str, list[Result]]:
        """(période, résultats du meilleur au moins bon) ; `only` : cette stratégie seule.
        Constaté : « compare Turtle sur tous les marchés » rejouait les 7 stratégies (1 min 52)."""
        key = (instrument.symbol, only)
        stamp, period, found = self._results.get(key, (0.0, "", []))
        if found and time.monotonic() - stamp < KEEP_SECONDS:
            return period, found
        hourly, daily = self.history(instrument)
        rules = load_rules(self.trading.rules_path)
        choice = getattr(self.trading, "choice", None)
        strategies = choice.available() if choice is not None else STRATEGIES
        strategies = tuple(s for s in strategies if s.covers(instrument)  # ses marchés
                           and (only is None or s.name == only))  # fmt: skip
        found = compare(hourly, daily, rules, spread_of(instrument, hourly[-1].close), strategies)
        period = f"du {hourly[0].time:%d/%m/%Y} au {hourly[-1].time:%d/%m/%Y}"
        self._results[key] = (time.monotonic(), period, found)
        return period, found

    def instruments(self, everything: bool, named: str) -> list[Instrument]:
        if named:
            return [risk_calc.resolve(named)]
        if not everything:
            return [self.trading.instrument_for("")]
        symbols = list(UNIVERSE)
        alerts = getattr(self.trading, "alerts", None)
        if alerts is not None:
            symbols += [a.symbol for a in alerts.store.all() if a.kind == "setup"]
        return [by_symbol(s) for s in dict.fromkeys(symbols)]

    def many(self, instruments: list[Instrument], only: str | None = None) -> list[tuple]:
        """[(marché, période, résultats ou l'erreur)…], plusieurs marchés lus à la fois."""
        from friday.trading.market import MarketUnavailable

        def one(item: Instrument) -> tuple:
            try:
                return (item, *(self.results(item, only) if only else self.results(item)))
            except MarketUnavailable as error:
                return item, "", error

        with ThreadPoolExecutor(LOADERS) as pool:
            return list(pool.map(one, instruments))


def _figures(r: Result) -> str:
    rep, daily = r.report, r.strategy.unit == "jour" and r.since is not None
    since = f", en journalier depuis {r.since:%Y}" if daily else ""
    return f"{r_text(rep.expectancy)} par trade sur {rep.count} trades{since}"


def _one(instrument: Instrument, period: str, results: list[Result], current: str) -> str:
    by = {v: [r for r in results if r.verdict == v] for v in (WORKED, PROMISING, FAILED)}
    parts = [f"Sur {instrument.name}, {period}"]
    if by[WORKED]:
        parts.append("a fonctionné : " + ", ".join(
            f"{r.strategy.label} ({_figures(r)}, positive sur les deux moitiés)"
            for r in by[WORKED]))  # fmt: skip
    else:
        parts.append("aucune stratégie n'a fonctionné de façon prouvée")
    if by[PROMISING]:
        parts.append("prometteuses mais pas prouvées : " + ", ".join(
            f"{r.strategy.label} ({_figures(r)}, {r.why()})" for r in by[PROMISING]))  # fmt: skip
    if by[FAILED]:
        parts.append(f"n'ont pas fonctionné : {', '.join(r.strategy.label for r in by[FAILED])}")
    mine = next((r for r in results if r.strategy.name == current), None)
    if mine is not None:
        parts.append(f"ta stratégie actuelle : {mine.strategy.label} ({mine.verdict})")
    return " ; ".join(parts) + "."


class CompareStrategiesTool(Tool):
    name = "compare_strategies"
    description = (
        "Compare les stratégies de la bibliothèque sur l'historique d'un instrument (ou de tous "
        "les marchés, aussi pour une seule stratégie) : lesquelles ont fonctionné (« compare les "
        "stratégies sur l'or », « compare Turtle sur tous les marchés »)."
    )
    parameters = {
        "instrument": {"type": "string", "description": "Seulement s'il en nomme un"},
        "everything": {"type": "boolean", "description": "true : tous les marchés"},
        "strategy": {"type": "string", "description": "La stratégie nommée, s'il en nomme une"},
        "request": {"type": "string", "description": "La phrase de l'utilisateur"},
    }
    timeout = 120

    def __init__(self, lab: StrategyLab, choice) -> None:
        self.lab, self.choice = lab, choice

    def label(self, args: dict) -> str:
        return "📚 Comparaison des stratégies"

    def run(self, instrument: str = "", everything: bool = False, strategy: str = "",
            request: str = "") -> ToolResult:  # fmt: skip
        try:
            chosen = self.lab.instruments(everything, instrument)
        except ValueError as error:
            return ToolResult(f"{error} Demande lequel.")
        if len(chosen) > 1:
            return self._markets(chosen, asked_strategy(self.choice, strategy, request))
        item = chosen[0]
        _, period, results = self.lab.many(chosen)[0]
        if isinstance(results, Exception):
            return ToolResult(f"Dis EXACTEMENT : « {item.name} : historique indisponible "
                              f"({results}). »")  # fmt: skip
        spoken = _one(item, period, results, self.choice.get(item.symbol).name)
        items = [{"text": f"{ICONS[r.verdict]} {item.name} · {r.strategy.label}",
                  "meta": f"{r.report.summary()}" + (f" — {r.why()}" if r.why() else "")
                  + (f" — journalier depuis {r.since:%Y}" if r.strategy.unit == "jour" else "")}
                 for r in results]  # fmt: skip
        return self._said(spoken, items)

    def _markets(self, chosen: list[Instrument], name: str | None) -> ToolResult:
        if name:  # une seule stratégie : ses marchés seulement, elle seule rejouée
            strategy = self.choice.named(name)
            chosen = [m for m in chosen if strategy.covers(m)] or chosen
        found = self.lab.many(chosen, name)
        markets = [(m, r) for m, _, r in found if not isinstance(r, Exception)]
        if not markets:
            return ToolResult("Dis EXACTEMENT : « Les historiques des marchés sont "
                              "indisponibles pour le moment (Yahoo). »")  # fmt: skip
        spoken, items = one_strategy(name, markets) if name else all_strategies(markets)
        if missing := [m.name for m, _, r in found if isinstance(r, Exception)]:
            spoken += f" Historique indisponible : {', '.join(missing)}."
        return self._said(spoken, items)

    def _said(self, spoken: str, items: list[dict]) -> ToolResult:
        return ToolResult(
            f"Dis EXACTEMENT : « {spoken} » Le détail est affiché. Le passé ne garantit rien.",
            Display("items", "Bibliothèque de stratégies", {"icon": "📚", "items": items}),
        )


class ChooseStrategyTool(Tool):
    name = "choose_strategy"
    description = (
        "Choisit la stratégie d'un instrument (« choisis la cassure de range pour l'or », "
        "« reviens à mon plan sur l'EUR/USD ») : celle des alertes, de la check-list et du "
        "briefing. Refusée si elle n'a pas fonctionné sur l'historique."
    )
    parameters = {
        "strategy": {"type": "string", "description": "La stratégie nommée"},
        "instrument": {"type": "string", "description": "Seulement s'il en nomme un"},
        "request": {"type": "string", "description": "La phrase de l'utilisateur"},
    }
    required = ("strategy",)
    timeout = 120

    def __init__(self, lab: StrategyLab, choice) -> None:
        self.lab, self.choice = lab, choice

    def run(self, strategy: str, instrument: str = "", request: str = "") -> ToolResult:
        from friday.trading.market import MarketUnavailable

        name = strategy_named(strategy)
        if name == "mon_plan":  # lequel de tes plans ? (nommé dans la phrase, sinon le premier)
            plan = self.choice.book.find(request or strategy)
            if plan is None:
                first = self.choice.first_plan()
                name = first.name if first else None
            elif plan["spec"]:
                name = PREFIX + plan["id"]
            else:
                return ToolResult(f"Dis EXACTEMENT : « Le plan « {plan['nom']} » n'est pas "
                                  "encore traduit en règles : dis « traduis le plan "
                                  f"{plan['nom']} ». »")  # fmt: skip
            if name is None:
                return ToolResult("Dis EXACTEMENT : « Aucun de tes plans écrits n'est encore "
                                  "traduit en règles : dis « traduis mon plan », ou utilise le "
                                  "bouton dans Réglages → Trading. »")  # fmt: skip
        if name is None:
            known = ", ".join(s.label for s in BY_NAME.values())
            return ToolResult(f"Dis EXACTEMENT : « Je ne connais pas cette stratégie. Celles de "
                              f"la bibliothèque : {known}. »")  # fmt: skip
        try:
            (item,) = self.lab.instruments(False, instrument)
            _, results = self.lab.results(item)
        except (ValueError, MarketUnavailable) as error:
            return ToolResult(f"Choix impossible : {error} Dis-le simplement.")
        found = next((r for r in results if r.strategy.name == name), None)
        if found is None:  # un plan qui ne suit pas cette famille de marchés
            return ToolResult("Dis EXACTEMENT : « Ce plan ne suit pas ce marché : coche sa "
                              "famille dans Réglages → Trading → Mes plans. »")  # fmt: skip
        label = found.strategy.label
        if found.verdict == FAILED and not name.startswith(PREFIX):
            spoken = (f"Je ne la mets pas : {label} n'a pas fonctionné sur {item.name} "
                      f"({_figures(found)}). Choisis une stratégie qui a fonctionné ou qui est "
                      "prometteuse, ou améliore ton plan écrit.")  # fmt: skip
            return ToolResult(f"Dis EXACTEMENT : « {spoken} »")
        self.choice.set(item.symbol, name)
        spoken = (f"C'est noté : sur {item.name}, les alertes, la check-list et le briefing "
                  f"suivent maintenant {label}.")  # fmt: skip
        if found.verdict == PROMISING:
            spoken += (f" Attention : elle est seulement prometteuse ({found.why()}) ; "
                       "teste-la d'abord en compte démo.")  # fmt: skip
        elif found.verdict == FAILED:
            spoken += (f" Attention : ton plan n'a pas fonctionné sur l'historique "
                       f"({_figures(found)}) ; à améliorer avant le réel.")  # fmt: skip
        return ToolResult(f"Dis EXACTEMENT : « {spoken} »")
