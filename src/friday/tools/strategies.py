"""Outils du mode trading : la bibliothèque de stratégies (T7). « Compare les stratégies sur
l'or » : chacune backtestée (même moteur, même spread, même risque) avec un verdict honnête ;
« choisis la cassure de range pour l'or » : elle devient celle des alertes, de la check-list
et du briefing (une stratégie qui n'a pas fonctionné est refusée). Tout sur le PC."""

import time

from friday.tools.backtest import load_history, spread_of
from friday.tools.base import Display, Tool, ToolResult
from friday.trading import risk_calc
from friday.trading.backtest.compare import FAILED, ICONS, PROMISING, WORKED, Result, compare
from friday.trading.backtest.report import r_text
from friday.trading.instruments import Instrument, by_symbol
from friday.trading.plan_rules import load_rules
from friday.trading.strategies import BY_NAME, strategy_named

KEEP_SECONDS = 3600
DEFAULT = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY")  # « tous mes instruments »


class StrategyLab:
    """L'historique et les comparaisons, gardés une heure (une comparaison : ~1 s)."""

    def __init__(self, trading, history=load_history) -> None:
        self.trading, self.history = trading, history
        self._results: dict[str, tuple[float, str, list[Result]]] = {}

    def results(self, instrument: Instrument) -> tuple[str, list[Result]]:
        """(période, résultats du meilleur au moins bon)."""
        stamp, period, found = self._results.get(instrument.symbol, (0.0, "", []))
        if found and time.monotonic() - stamp < KEEP_SECONDS:
            return period, found
        hourly, daily = self.history(instrument)
        rules = load_rules(self.trading.rules_path)
        found = compare(hourly, daily, rules, spread_of(instrument, hourly[-1].close))
        period = f"du {hourly[0].time:%d/%m/%Y} au {hourly[-1].time:%d/%m/%Y}"
        self._results[instrument.symbol] = (time.monotonic(), period, found)
        return period, found

    def instruments(self, everything: bool, named: str) -> list[Instrument]:
        if named:
            return [risk_calc.resolve(named)]
        if not everything:
            return [self.trading.instrument_for("")]
        symbols = list(DEFAULT)
        alerts = getattr(self.trading, "alerts", None)
        if alerts is not None:
            symbols += [a.symbol for a in alerts.store.all() if a.kind == "setup"]
        return [by_symbol(s) for s in dict.fromkeys(symbols)]


def _figures(r: Result) -> str:
    rep = r.report
    return f"{r_text(rep.expectancy)} par trade sur {rep.count} trades"


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
    mine = next(r for r in results if r.strategy.name == current)
    parts.append(f"ta stratégie actuelle : {mine.strategy.label} ({mine.verdict})")
    return " ; ".join(parts) + "."


class CompareStrategiesTool(Tool):
    name = "compare_strategies"
    description = (
        "Compare les stratégies de la bibliothèque sur l'historique d'un instrument (ou de tous "
        "ses instruments) : lesquelles ont fonctionné (« compare les stratégies sur l'or », "
        "« quelle stratégie marche sur l'EUR/USD ? »)."
    )
    parameters = {
        "instrument": {"type": "string", "description": "Seulement s'il en nomme un"},
        "everything": {"type": "boolean", "description": "true : tous ses instruments"},
    }
    timeout = 120

    def __init__(self, lab: StrategyLab, choice) -> None:
        self.lab, self.choice = lab, choice

    def label(self, args: dict) -> str:
        return "📚 Comparaison des stratégies"

    def run(self, instrument: str = "", everything: bool = False) -> ToolResult:
        from friday.trading.market import MarketUnavailable

        try:
            chosen = self.lab.instruments(everything, instrument)
        except ValueError as error:
            return ToolResult(f"{error} Demande lequel.")
        said, items = [], []
        for item in chosen:
            try:
                period, results = self.lab.results(item)
            except MarketUnavailable as error:
                said.append(f"{item.name} : historique indisponible ({error})")
                continue
            current = self.choice.get(item.symbol).name
            said.append(_one(item, period, results, current) if len(chosen) == 1
                        else _short(item, results))  # fmt: skip
            items += [{"text": f"{ICONS[r.verdict]} {item.name} · {r.strategy.label}",
                       "meta": f"{r.report.summary()}" + (f" — {r.why()}" if r.why() else "")}
                      for r in results]  # fmt: skip
        spoken = (
            " ".join(said)
            if len(chosen) == 1
            else "Comparaison des stratégies : " + " ; ".join(said) + "."
        )
        return ToolResult(
            f"Dis EXACTEMENT : « {spoken} » Le détail est affiché. Le passé ne garantit rien.",
            Display("items", "Bibliothèque de stratégies", {"icon": "📚", "items": items}),
        )


def _short(instrument: Instrument, results: list[Result]) -> str:
    best = results[0]
    if best.verdict == FAILED:
        return f"{instrument.name} : aucune n'a fonctionné"
    return f"{instrument.name} : {best.strategy.label} {best.verdict} ({_figures(best)})"


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
    }
    required = ("strategy",)
    timeout = 120

    def __init__(self, lab: StrategyLab, choice) -> None:
        self.lab, self.choice = lab, choice

    def run(self, strategy: str, instrument: str = "") -> ToolResult:
        from friday.trading.market import MarketUnavailable

        name = strategy_named(strategy)
        if name is None:
            known = ", ".join(s.label for s in BY_NAME.values())
            return ToolResult(f"Dis EXACTEMENT : « Je ne connais pas cette stratégie. Celles de "
                              f"la bibliothèque : {known}. »")  # fmt: skip
        try:
            (item,) = self.lab.instruments(False, instrument)
            _, results = self.lab.results(item)
        except (ValueError, MarketUnavailable) as error:
            return ToolResult(f"Choix impossible : {error} Dis-le simplement.")
        found = next(r for r in results if r.strategy.name == name)
        label = found.strategy.label
        if found.verdict == FAILED and name != "plan":
            spoken = (f"Je ne la mets pas : {label} n'a pas fonctionné sur {item.name} "
                      f"({_figures(found)}). Garde ton plan, ou choisis une stratégie qui a "
                      "fonctionné ou qui est prometteuse.")  # fmt: skip
            return ToolResult(f"Dis EXACTEMENT : « {spoken} »")
        self.choice.set(item.symbol, name)
        spoken = (f"C'est noté : sur {item.name}, les alertes, la check-list et le briefing "
                  f"suivent maintenant {label}.")  # fmt: skip
        if found.verdict == PROMISING:
            spoken += (f" Attention : elle est seulement prometteuse ({found.why()}) ; "
                       "teste-la d'abord en compte démo.")  # fmt: skip
        elif found.verdict == FAILED:
            spoken += f" Rappel : ton plan n'a pas fonctionné sur l'historique ({_figures(found)})."
        return ToolResult(f"Dis EXACTEMENT : « {spoken} »")
