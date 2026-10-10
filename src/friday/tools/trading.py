"""Outils locaux du mode trading : calculs de risque (déterministes). Rien ne part en ligne ;
le modèle local ne fait qu'extraire les chiffres de la demande. Le journal : trading_journal.py."""

from friday.tools.base import Tool, ToolResult
from friday.trading import risk_calc


def _n(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


INSTRUMENT = {"type": "string", "description": "« EUR/USD », « or », « XAUUSD », « AAPL »…"}
PRICE = {"type": "number", "description": "Cours actuel, SEULEMENT si l'utilisateur le donne"}


class Prices:
    """Cours manquants récupérés d'office (déterministe) : Yahoo pour l'instrument, BCE pour
    la conversion vers la devise du compte. Remplaçable dans les tests."""

    def price(self, instrument) -> float:
        from friday.trading.market import MarketUnavailable, fetch

        try:
            return fetch(instrument.yahoo, "1d", "5d")[0].price
        except MarketUnavailable as error:
            raise risk_calc.MissingRate(str(error)) from error

    def rate(self, quote: str, account: str) -> float:
        from friday.trading.reference_rates import RatesUnavailable, reference_rate

        try:
            return reference_rate(quote, account)[0]
        except RatesUnavailable as error:
            raise risk_calc.MissingRate(str(error)) from error


def value_per_lot(
    instrument, account: str, price: float | None, prices: Prices
) -> tuple[float, str]:
    """Valeur d'un pip pour 1 lot, en devise du compte, et d'où vient la conversion."""
    try:
        return risk_calc.pip_value(instrument, 1, account, price), ""
    except risk_calc.MissingRate:
        pass
    if instrument.kind == "forex" and instrument.symbol[:3] == account:
        price = prices.price(instrument)
        return risk_calc.pip_value(instrument, 1, account, price), f" (cours {price} récupéré)"
    rate = prices.rate(instrument.quote, account)
    value = risk_calc.pip_value(instrument, 1, account, quote_to_account=rate)
    return value, f" (conversion {instrument.quote}/{account} {rate} : cours BCE)"


def unit(instrument) -> str:
    return "titre(s)" if instrument.kind == "action" else "lot(s)"


def pip_words(instrument) -> str:
    unit = "pip" if instrument.kind == "forex" else "point"
    return (
        f"1 {unit} = {instrument.pip:g} {instrument.quote}, 1 lot = {instrument.contract:g} unités"
    )


class PositionSizeTool(Tool):
    name = "position_size"
    description = (
        "Calcule la taille de position (en lots) pour risquer un pourcentage du capital, avec un "
        "stop en pips / points OU des prix d'entrée et de stop. Tout instrument (forex, or, "
        "actions…). N'invente aucun chiffre : demande ceux qui manquent."
    )
    parameters = {
        "instrument": INSTRUMENT,
        "capital": {"type": "number", "description": "Capital du compte"},
        "risk_percent": {"type": "number", "description": "Risque par trade, en % (ex. 1)"},
        "stop_pips": {"type": "number", "description": "Distance du stop, en pips / points"},
        "entry": {"type": "number", "description": "Prix d'entrée (si le stop est donné en prix)"},
        "stop": {"type": "number", "description": "Prix du stop (si donné en prix)"},
        "price": PRICE,
    }
    required = ("instrument", "capital", "risk_percent")

    def __init__(self, account: str, prices: Prices | None = None) -> None:
        self.account, self.prices = account, prices or Prices()

    def run(self, instrument: str, capital: float, risk_percent: float,
            stop_pips: float | None = None, entry: float | None = None,
            stop: float | None = None, price: float | None = None) -> ToolResult:  # fmt: skip
        try:
            item = risk_calc.resolve(instrument)
            if not stop_pips and entry and stop:
                stop_pips = risk_calc.stop_in_pips(item, entry, stop)
            if not stop_pips:
                return ToolResult("Il manque la distance du stop (en pips / points, ou les prix "
                                  "d'entrée et de stop) : demande-la.")  # fmt: skip
            per_lot, origin = value_per_lot(item, self.account, price or entry, self.prices)
            size = risk_calc.position_size(capital, risk_percent, stop_pips, per_lot)
        except ValueError as error:
            return ToolResult(f"Calcul impossible : {error}")
        return ToolResult(
            f"Calcul exact (fait sur le PC) : {_n(size.lots)} {unit(item)} sur {item.label}, "
            f"stop à {_n(stop_pips, 1)} pips/points. Perte si le stop est touché : "
            f"{_n(size.risked)} {self.account} (maximum accepté : {_n(size.max_loss)} "
            f"{self.account}, soit {_n(risk_percent, 1)} %). Valeur d'un pip/point pour 1 lot : "
            f"{_n(per_lot)} {self.account}{origin}. Convention : {pip_words(item)} (vérifie "
            "celle de ton courtier). Donne ces chiffres tels quels."
        )


class PipValueTool(Tool):
    name = "pip_value"
    description = (
        "Calcule la valeur d'un pip / point pour un instrument et un nombre de lots (le cours "
        "est récupéré tout seul : ne le demande pas)."
    )
    parameters = {
        "instrument": INSTRUMENT,
        "lots": {"type": "number", "description": "Nombre de lots"},
    }  # pas de « price » : qwen le demandait toujours au lieu de calculer (constaté, T8)
    required = ("instrument", "lots")

    def __init__(self, account: str, prices: Prices | None = None) -> None:
        self.account, self.prices = account, prices or Prices()

    def run(self, instrument: str, lots: float, price: float | None = None) -> ToolResult:
        try:
            item = risk_calc.resolve(instrument)
            per_lot, origin = value_per_lot(item, self.account, price, self.prices)
        except ValueError as error:
            return ToolResult(f"Calcul impossible : {error}")
        return ToolResult(
            f"Calcul exact : 1 pip/point sur {_n(lots)} lot(s) de {item.label} vaut "
            f"{_n(per_lot * lots)} {self.account}{origin}. Convention : {pip_words(item)}. "
            "Donne ce chiffre tel quel."
        )


class RiskRewardTool(Tool):
    name = "risk_reward"
    description = "Calcule le ratio risque/rendement d'un trade (entrée, stop, objectif)."
    parameters = {
        "instrument": INSTRUMENT,
        "entry": {"type": "number", "description": "Prix d'entrée"},
        "stop": {"type": "number", "description": "Stop loss"},
        "target": {"type": "number", "description": "Objectif (take profit)"},
    }
    required = ("instrument", "entry", "stop", "target")

    def run(self, instrument: str, entry: float, stop: float, target: float) -> ToolResult:
        try:
            rr = risk_calc.risk_reward(instrument, entry, stop, target)
        except ValueError as error:
            return ToolResult(f"Calcul impossible : {error}")
        return ToolResult(
            f"Calcul exact : {rr.direction}, risque {_n(rr.risk_pips, 1)} pips, gain potentiel "
            f"{_n(rr.reward_pips, 1)} pips, ratio 1 pour {_n(rr.ratio)}. "
            "Donne ces chiffres tels quels."
        )
