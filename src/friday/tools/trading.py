"""Outils locaux du mode trading : calculs de risque (déterministes) et journal. Rien ne part
en ligne ; le modèle local ne fait qu'extraire les chiffres de la demande."""

from friday.tools.base import Tool, ToolResult
from friday.trading import risk_calc
from friday.trading.journal import TradeJournal


def _n(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


PAIR = {"type": "string", "description": "La paire (« EUR/USD »)"}
PRICE = {"type": "number", "description": "Cours actuel de la paire, si l'utilisateur le donne"}


class PositionSizeTool(Tool):
    name = "position_size"
    description = (
        "Calcule la taille de position (en lots) pour risquer un pourcentage du capital avec un "
        "stop donné en pips. N'invente aucun chiffre : demande ceux qui manquent."
    )
    parameters = {
        "pair": PAIR,
        "capital": {"type": "number", "description": "Capital du compte"},
        "risk_percent": {"type": "number", "description": "Risque par trade, en % (ex. 1)"},
        "stop_pips": {"type": "number", "description": "Distance du stop, en pips"},
        "price": PRICE,
    }
    required = ("pair", "capital", "risk_percent", "stop_pips")

    def __init__(self, account: str) -> None:
        self.account = account

    def run(self, pair: str, capital: float, risk_percent: float, stop_pips: float,
            price: float | None = None) -> ToolResult:  # fmt: skip
        try:
            per_lot = risk_calc.pip_value(pair, 1, self.account, price)
            size = risk_calc.position_size(capital, risk_percent, stop_pips, per_lot)
        except ValueError as error:
            return ToolResult(f"Calcul impossible : {error}")
        return ToolResult(
            f"Calcul exact (fait sur le PC) : {_n(size.lots)} lot(s) sur {pair.upper()}. Perte "
            f"si le stop est touché : {_n(size.risked)} {self.account} (maximum accepté : "
            f"{_n(size.max_loss)} {self.account}, soit {_n(risk_percent, 1)} %). Valeur du pip "
            f"pour 1 lot : {_n(per_lot)} {self.account}. Donne ces chiffres tels quels."
        )


class PipValueTool(Tool):
    name = "pip_value"
    description = "Calcule la valeur d'un pip pour une paire et un nombre de lots."
    parameters = {"pair": PAIR, "lots": {"type": "number", "description": "Nombre de lots"},
                  "price": PRICE}  # fmt: skip
    required = ("pair", "lots")

    def __init__(self, account: str) -> None:
        self.account = account

    def run(self, pair: str, lots: float, price: float | None = None) -> ToolResult:
        try:
            value = risk_calc.pip_value(pair, lots, self.account, price)
        except ValueError as error:
            return ToolResult(f"Calcul impossible : {error}")
        return ToolResult(
            f"Calcul exact : 1 pip sur {_n(lots)} lot(s) de {pair.upper()} vaut "
            f"{_n(value)} {self.account}. Donne ce chiffre tel quel."
        )


class RiskRewardTool(Tool):
    name = "risk_reward"
    description = "Calcule le ratio risque/rendement d'un trade (entrée, stop, objectif)."
    parameters = {
        "pair": PAIR,
        "entry": {"type": "number", "description": "Prix d'entrée"},
        "stop": {"type": "number", "description": "Stop loss"},
        "target": {"type": "number", "description": "Objectif (take profit)"},
    }
    required = ("pair", "entry", "stop", "target")

    def run(self, pair: str, entry: float, stop: float, target: float) -> ToolResult:
        try:
            rr = risk_calc.risk_reward(pair, entry, stop, target)
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
        "pair": PAIR,
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
