"""Outil du mode trading : les dernières analyses de Claude et ce que le cours a fait depuis
(« mes dernières analyses », « tes analyses sur l'or »). Local : rien ne part en ligne, sauf
la lecture des cours publics (Yahoo)."""

import logging
from collections.abc import Callable
from datetime import datetime

from friday.tools.base import Display, Tool, ToolResult
from friday.trading import risk_calc
from friday.trading.analysis_memory import moved
from friday.trading.instruments import by_symbol
from friday.trading.market import MarketUnavailable

log = logging.getLogger(__name__)


class PastAnalysesTool(Tool):
    name = "past_analyses"
    description = (
        "Les dernières analyses de Claude et ce que le cours a fait depuis (« mes dernières "
        "analyses », « tes analyses sur l'or ont-elles marché ? »)."
    )
    parameters = {"instrument": {"type": "string",
                                 "description": "Seulement s'il nomme un instrument"}}  # fmt: skip

    def __init__(self, journal, price: Callable) -> None:
        """`price(instrument)` : cours Yahoo actuel (comme celui gardé à l'envoi)."""
        self.journal, self.price = journal, price

    def label(self, args: dict) -> str:
        return "🧠 Analyses passées"

    def run(self, instrument: str = "") -> ToolResult:
        try:
            symbol = risk_calc.resolve(instrument).symbol if instrument else None
        except ValueError as error:
            return ToolResult(f"{error} Demande lequel.")
        found = self.journal.analyses(symbol, limit=5)
        if not found:
            return ToolResult("Dis EXACTEMENT : « Aucune analyse de Claude enregistrée pour "
                              "l'instrument demandé. »")  # fmt: skip
        now: dict[str, float | None] = {}
        items, said = [], []
        for a in found:
            item = by_symbol(a.instrument) if a.instrument else None
            if item is not None and a.instrument not in now:
                try:
                    now[a.instrument] = self.price(item)
                except MarketUnavailable as error:
                    log.info("Cours indisponible : %s", error)
                    now[a.instrument] = None
            since = moved(a.price, now.get(a.instrument)) if item else ""
            when = f"{datetime.fromisoformat(a.sent_at):%d/%m à %H:%M}"
            name = item.name if item else "sans instrument"
            items.append({"text": f"{when} · {name}{since.replace(' ; depuis, le', ' · le')}",
                          "meta": f"« {a.question} » — {a.answer[:400]}"})  # fmt: skip
            said.append(f"le {when}, {name}{since}")
        head = "Ta dernière analyse" if len(found) == 1 else f"Tes {len(found)} dernières analyses"
        spoken = f"{head} : " + " ; ".join(said) + "."
        return ToolResult(
            f"Dis EXACTEMENT : « {spoken} » Le détail des réponses est affiché.",
            Display("items", "Analyses de Claude", {"icon": "🧠", "items": items}),
        )
