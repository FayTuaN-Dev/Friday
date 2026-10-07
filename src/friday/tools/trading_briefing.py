"""Outil du mode trading : le briefing trading à la demande (« briefing trading », « prépare ma
journée de trading », « briefing trading sur l'argent »). Calculé sur le PC (trading/briefing)."""

from friday.tools.base import Display, Tool, ToolResult
from friday.trading import risk_calc
from friday.trading.briefing import TradingBriefing


def briefing_result(briefing: TradingBriefing, automatic: bool = False) -> ToolResult:
    items = [{"text": title, "meta": text} for title, text in briefing.parts]
    intro = "(Briefing trading automatique, début de ta plage de trading.) " if automatic else ""
    return ToolResult(
        f"{intro}Dis EXACTEMENT ce texte, sans rien changer ni ajouter : « {briefing.text()} »",
        Display("items", "Briefing trading", {"icon": "🌅", "items": items}),
    )


class TradingBriefingTool(Tool):
    name = "trading_briefing"
    description = (
        "Briefing trading : annonces fortes du jour, mouvement de la nuit, niveaux clés, "
        "tendance et règles du plan (« briefing trading », « prépare ma journée de trading »)."
    )
    parameters = {
        "instrument": {
            "type": "string",
            "description": "Laisse VIDE, sauf si l'utilisateur nomme lui-même un instrument dans "
            "sa phrase (vide : ceux de ses réglages)",
        }
    }
    timeout = 90

    def __init__(self, service) -> None:
        self.service = service

    def label(self, args: dict) -> str:
        return "🌅 Briefing trading"

    def run(self, instrument: str = "") -> ToolResult:
        try:
            chosen = [risk_calc.resolve(instrument)] if instrument else None
        except ValueError as error:
            return ToolResult(f"Briefing impossible : {error}")
        return briefing_result(self.service.build(chosen))
