"""Outils locaux du mode trading : calculs de risque (déterministes) et journal. Rien ne part
en ligne ; le modèle local ne fait qu'extraire les chiffres de la demande."""

from friday.tools.base import Tool, ToolResult
from friday.trading import risk_calc
from friday.trading.journal import TradeJournal


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
    description = "Calcule la valeur d'un pip / point pour un instrument et un nombre de lots."
    parameters = {
        "instrument": INSTRUMENT,
        "lots": {"type": "number", "description": "Nombre de lots"},
        "price": PRICE,
    }
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


class LogTradeTool(Tool):
    name = "log_trade"
    description = "Note un trade dans le journal de trading local (paire, sens, entrée, stop…)."
    parameters = {
        "pair": INSTRUMENT,
        "direction": {"type": "string", "enum": ["achat", "vente"]},
        "entry": {"type": "number", "description": "Prix d'entrée"},
        "stop": {"type": "number", "description": "Stop loss"},
        "target": {"type": "number", "description": "Objectif, s'il est donné"},
        "lots": {"type": "number", "description": "Taille, si elle est donnée"},
        "reason": {"type": "string", "description": "Raison du trade, avec ses mots"},
    }
    required = ("pair", "direction", "entry", "stop")

    def __init__(self, journal: TradeJournal) -> None:
        self.journal = journal

    def run(self, pair: str, direction: str, entry: float, stop: float, target: float | None = None,
            lots: float | None = None, reason: str = "") -> ToolResult:  # fmt: skip
        trade = self.journal.open_trade(pair, direction, entry, stop, target, lots, reason)
        return ToolResult(f"Trade n°{trade.id} noté dans le journal (local) : {direction} "
                          f"{trade.pair} à {entry}, stop {stop}.")  # fmt: skip


class CloseTradeTool(Tool):
    name = "close_trade"
    description = "Clôture un trade du journal avec son prix de sortie (résultat calculé en R)."
    parameters = {
        "trade_id": {"type": "integer", "description": "Numéro du trade"},
        "exit_price": {"type": "number", "description": "Prix de sortie"},
    }
    required = ("trade_id", "exit_price")

    def __init__(self, journal: TradeJournal) -> None:
        self.journal = journal

    def run(self, trade_id: int, exit_price: float) -> ToolResult:
        trade = self.journal.close_trade(int(trade_id), exit_price)
        if trade is None:
            return ToolResult(f"Pas de trade n°{trade_id} en cours dans le journal.")
        return ToolResult(f"Trade n°{trade.id} clôturé : {trade.result_r:+.2f} R.")


class TradeStatsTool(Tool):
    name = "trade_stats"
    description = "Bilan du journal de trading et derniers trades (« mon bilan », « mes trades »)."
    parameters = {}

    def __init__(self, journal: TradeJournal) -> None:
        self.journal = journal

    def run(self) -> ToolResult:
        lines = [
            f"- n°{t.id} {t.direction} {t.pair} à {t.entry} (stop {t.stop}) : "
            + (f"{t.result_r:+.2f} R" if t.result_r is not None else "en cours")
            for t in self.journal.recent(5)
        ]
        return ToolResult(self.journal.summary() + ("\nDerniers :\n" + "\n".join(lines)
                                                     if lines else ""))  # fmt: skip
