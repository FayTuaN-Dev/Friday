"""Outil du mode trading : le backtest du plan (« teste mon plan sur l'or »). Les règles
chiffrées (Réglages → Trading) rejouées sur ~2 ans et demi de bougies 1 h (Yahoo), plus des
variantes qui ne changent qu'une règle. Tout est calculé sur le PC ; rien ne part chez Claude."""

import time
from dataclasses import replace

from friday.tools.base import Display, Tool, ToolResult
from friday.tools.trading import INSTRUMENT
from friday.trading import Trading, risk_calc
from friday.trading.backtest.engine import simulate
from friday.trading.backtest.report import FEW, Report, r_text, variants
from friday.trading.instruments import Instrument
from friday.trading.market import Candle, MarketUnavailable, fetch
from friday.trading.plan_rules import load_rules

KEEP_SECONDS = 3600  # l'historique est gardé une heure en mémoire
SPREAD_PIPS = {"forex": 1, "metal": 3, "energie": 3, "indice": 1}  # spread typique
SPREAD_SHARE = 0.0005  # crypto, actions : 0,05 % du cours


def load_history(instrument: Instrument) -> tuple[list[Candle], list[Candle]]:
    """(bougies 1 h sur 730 jours, bougies journalières sur 5 ans pour l'EMA200)."""
    _, hourly = fetch(instrument.yahoo, "1h", "730d")
    _, daily = fetch(instrument.yahoo, "1d", "5y")
    return hourly, daily


def spread_of(instrument: Instrument, price: float) -> float:
    pips = SPREAD_PIPS.get(instrument.kind)
    return pips * instrument.pip if pips else price * SPREAD_SHARE


def _variant_label(objectif: float | None, stop: float | None) -> str:
    changes = [f"objectif {objectif:g} R" if objectif else "", f"stop {stop:g} ATR" if stop else ""]
    return f"Ta variante ({', '.join(c for c in changes if c)})".replace(".", ",")


class BacktestTool(Tool):
    name = "backtest_plan"
    description = (
        "Backtest : rejoue les règles du plan de trading de l'utilisateur sur l'historique "
        "(« teste mon plan sur l'or », « mon plan aurait-il gagné sur l'EUR/USD ? », « et avec un "
        "objectif à 3 R ? »). Donne trades, % gagnants, gain moyen en R, pire série, et compare "
        "des variantes du plan."
    )
    parameters = {
        "instrument": INSTRUMENT,
        "objectif": {"type": "number", "description": "Objectif en R à essayer, s'il est demandé"},
        "stop": {
            "type": "number",
            "description": "Stop minimal en ATR à essayer, s'il est demandé",
        },
        "plan": {"type": "string", "description": "Le plan écrit nommé, s'il en nomme un"},
    }
    timeout = 120

    def __init__(self, trading: Trading, history=load_history) -> None:
        self.trading, self.history = trading, history
        self._cache: dict[str, tuple[float, tuple]] = {}

    def label(self, args: dict) -> str:
        return f"🧪 Backtest du plan : {args.get('instrument', '')}".strip(" :")

    def run(self, instrument: str = "", objectif: float | None = None,
            stop: float | None = None, plan: str = "") -> ToolResult:  # fmt: skip
        """`objectif` (en R) et `stop` (en ATR) : la variante demandée (« et avec 3 R ? »)."""
        try:
            item = risk_calc.resolve(instrument) if instrument else self.trading.instrument_for("")
        except ValueError as error:
            return ToolResult(f"Backtest impossible : {error}")
        if item is None:
            return ToolResult("Quel instrument ? Demande-le.")
        try:
            hourly, daily = self._load(item)
        except MarketUnavailable as error:
            return ToolResult(f"Backtest impossible : {error} Dis-le simplement.")
        rules = load_rules(self.trading.rules_path)
        choice = getattr(self.trading, "choice", None)
        strategy = choice.get(item.symbol) if choice is not None else None
        if plan and choice is not None:  # « teste le plan Cassure Londres »
            found = choice.book.get(plan) or choice.book.find(plan)
            if found is None or not found["spec"]:
                return ToolResult("Dis EXACTEMENT : « Ce plan n'existe pas ou n'est pas encore "
                                  "traduit en règles. »")  # fmt: skip
            strategy = choice.book.strategy(found)
        if strategy is None or strategy.name == "repli":
            runs = variants(rules)  # le modèle : chaque règle d'entrée se fait varier
            if strategy is not None:
                runs[0] = (strategy.label[0].upper() + strategy.label[1:], rules)
        else:  # ton plan écrit, ou une autre stratégie : elle seule (« compare » pour le reste)
            runs = [(strategy.label[0].upper() + strategy.label[1:], rules)]
        if objectif or stop:
            mine = replace(rules, min_rr=objectif or rules.min_rr, stop_atr=stop or rules.stop_atr)
            runs.insert(1, (_variant_label(objectif, stop), mine))
        spread = spread_of(item, hourly[-1].close)
        reports = [Report(label, simulate(hourly, daily, r, spread, strategy))
                   for label, r in runs]  # fmt: skip
        return self._result(item, hourly, reports)

    def _load(self, item: Instrument):
        stamp, data = self._cache.get(item.yahoo, (0.0, None))
        if data is None or time.monotonic() - stamp > KEEP_SECONDS:
            data = self.history(item)
            self._cache[item.yahoo] = (time.monotonic(), data)
        return data

    def _result(self, item: Instrument, hourly: list[Candle], reports: list[Report]) -> ToolResult:
        plan = reports[0]
        period = f"du {hourly[0].time:%d/%m/%Y} au {hourly[-1].time:%d/%m/%Y}"
        spoken = f"Sur {item.name}, {period}, en bougies 1 h : {plan.short()}"
        if plan.count and plan.count < FEW:
            spoken += f". Attention : moins de {FEW} trades, c'est trop peu pour conclure"
        better = [r for r in reports[1:] if r.count >= FEW and plan.count >= FEW
                  and r.expectancy - plan.expectancy > max(r.margin, plan.margin)]  # fmt: skip
        if better:
            best = max(better, key=lambda r: r.expectancy)
            verb = "fait mieux" if best.expectancy > 0 else "perd moins"
            spoken += (f". La variante « {best.label} » {verb}, au-delà du hasard : "
                       f"{r_text(best.expectancy)} par trade en moyenne")  # fmt: skip
        elif plan.count >= FEW and len(reports) > 1:
            spoken += ". Aucune variante ne fait nettement mieux : les écarts restent dans la marge"
            spoken += " du hasard"
        mine = next((r for r in reports if r.label.startswith("Ta variante")), None)
        if mine is not None:
            spoken += f". {mine.label} : {mine.short()}"
        spoken += "."
        items = [{"text": r.label, "meta": r.summary()} for r in reports]
        items.append({"text": "Comment c'est calculé", "meta": (
            "Entrée à la clôture 1 h quand toutes les règles sont réunies ; stop sous le dernier "
            "creux (au moins N ATR), objectif en R ; stop compté si les deux sont touchés dans la "
            "même bougie ; spread déduit ; un trade à la fois. Annonces et risque en % non "
            "rejoués. Le passé ne garantit rien.")})  # fmt: skip
        detail = "\n".join(r.line() for r in reports)
        return ToolResult(
            f"Backtest fait sur le PC ({period}) :\n{detail}\n"
            f"Dis EXACTEMENT cette phrase, sans rien ajouter sur les chiffres : « {spoken} » "
            "Puis, en quelques mots, que le passé ne garantit rien ; le détail est affiché.",
            Display("items", f"Backtest du plan : {item.name}", {"icon": "🧪", "items": items}),
        )
