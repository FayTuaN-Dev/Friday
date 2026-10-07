"""Outils du journal de trading (local) : noter un trade avec son setup, le respect du plan et
l'état d'esprit (plus une capture du graphique si TradingView l'affiche), le compléter après
coup, le clôturer, le bilan avec ce qu'il apprend, et l'ouvrir à l'écran."""

import logging
from collections.abc import Callable
from pathlib import Path

from friday.tools.base import Display, Tool, ToolResult
from friday.trading import risk_calc
from friday.trading.journal import TradeJournal
from friday.trading.journal_export import save_capture
from friday.trading.journal_stats import MOODS, lessons

log = logging.getLogger(__name__)
INSTRUMENT = {"type": "string", "description": "« EUR/USD », « or », « XAUUSD », « AAPL »…"}
NOTES = {
    "setup": {"type": "string", "description": "Le setup utilisé (« repli EMA50 »…), s'il le dit"},
    "plan_respected": {"type": "boolean", "description": "Plan respecté ? Seulement s'il le dit"},
    "mood": {"type": "string",
             "description": f"État d'esprit, s'il le dit : {', '.join(MOODS)}…"},
}  # fmt: skip
Snapshot = Callable[[str], bytes | None]  # symbole → PNG du graphique, ou None


class LogTradeTool(Tool):
    name = "log_trade"
    description = (
        "Note un trade dans le journal de trading local (instrument, sens, entrée, stop… et, "
        "s'il les dit : setup, plan respecté, état d'esprit)."
    )
    parameters = {
        "pair": INSTRUMENT,
        "direction": {"type": "string", "enum": ["achat", "vente"]},
        "entry": {"type": "number", "description": "Prix d'entrée"},
        "stop": {"type": "number", "description": "Stop loss"},
        "target": {"type": "number", "description": "Objectif, s'il est donné"},
        "lots": {"type": "number", "description": "Taille, si elle est donnée"},
        "reason": {
            "type": "string",
            "description": "Raison du trade, SEULEMENT si l'utilisateur la donne (ses "
            "mots) ; sinon ne mets rien, n'invente jamais",
        },
        **NOTES,
    }
    required = ("pair", "direction", "entry", "stop")

    def __init__(self, journal: TradeJournal, snapshot: Snapshot | None = None,
                 folder: Path | None = None) -> None:  # fmt: skip
        self.journal, self.snapshot, self.folder = journal, snapshot, folder

    def run(self, pair: str, direction: str, entry: float, stop: float, target: float | None = None,
            lots: float | None = None, reason: str = "", setup: str = "",
            plan_respected: bool | None = None, mood: str = "") -> ToolResult:  # fmt: skip
        try:  # « l'or » → XAUUSD (constaté : il était noté « OR », hors des statistiques)
            pair = risk_calc.resolve(pair).symbol
        except ValueError:
            pass
        trade = self.journal.open_trade(pair, direction, entry, stop, target, lots, reason,
                                        setup, plan_respected, mood)  # fmt: skip
        shot = ""
        if self.snapshot is not None and self.folder is not None:
            try:
                image = self.snapshot(trade.pair)
            except Exception as error:  # pas de capture : le trade est noté quand même
                log.info("Capture d'entrée impossible : %s", error)
                image = None
            if image:
                self.journal.annotate(trade.id, capture=save_capture(self.folder, trade.id, image))
                shot = " Capture du graphique gardée."
        missing = [w for w, v in (("le setup", setup), ("si le plan est respecté", plan_respected),
                                  ("ton état d'esprit", mood)) if v in ("", None)]  # fmt: skip
        ask = f" Demande-lui en une phrase {', '.join(missing)}." if missing else ""
        return ToolResult(f"Trade n°{trade.id} noté dans le journal (local) : {direction} "
                          f"{trade.pair} à {entry}, stop {stop}.{shot}{ask}")  # fmt: skip


class AnnotateTradeTool(Tool):
    name = "annotate_trade"
    description = (
        "Complète un trade du journal : setup, plan respecté ou non, état d'esprit (« le trade 3 "
        "c'était un repli EMA50, plan respecté, j'étais stressé »)."
    )
    parameters = {"trade_id": {"type": "integer", "description": "Numéro du trade"}, **NOTES}
    required = ("trade_id",)

    def __init__(self, journal: TradeJournal) -> None:
        self.journal = journal

    def run(self, trade_id: int, setup: str = "", plan_respected: bool | None = None,
            mood: str = "") -> ToolResult:  # fmt: skip
        trade = self.journal.annotate(int(trade_id), setup=setup or None, plan_ok=plan_respected,
                                      mood=mood or None)  # fmt: skip
        if trade is None:
            return ToolResult(f"Pas de trade n°{trade_id} dans le journal.")
        return ToolResult(f"Trade n°{trade.id} complété. Dis-le en une phrase.")


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
    description = (
        "Bilan du journal de trading et ce qu'il apprend : setups, heures, états d'esprit qui "
        "marchent ou coûtent (« mon bilan », « qu'est-ce qui marche dans mes trades ? »)."
    )
    parameters = {}

    def __init__(self, journal: TradeJournal) -> None:
        self.journal = journal

    def run(self) -> ToolResult:
        trades = self.journal.all_trades()
        found = lessons(trades)
        spoken = self.journal.summary() + (" " + " ".join(found[:3]) if found else "")
        recent = [
            f"- n°{t.id} {t.direction} {t.pair} à {t.entry} (stop {t.stop}) : "
            + (f"{t.result_r:+.2f} R" if t.result_r is not None else "en cours")
            for t in trades[:5]
        ]
        return ToolResult(
            f"Dis EXACTEMENT : « {spoken} »"
            + (
                "\nDerniers trades (pour répondre si on te les demande) :\n" + "\n".join(recent)
                if recent
                else ""
            )  # fmt: skip
        )


class OpenJournalTool(Tool):
    name = "open_journal"
    description = "Ouvre la fenêtre du journal de trading (« ouvre mon journal », « mes trades »)."
    parameters = {}

    def label(self, args: dict) -> str:
        return "📒 Journal de trading"

    def run(self) -> ToolResult:
        return ToolResult(
            "Journal ouvert. Dis-le en une phrase.", Display("journal", "Journal de trading")
        )
