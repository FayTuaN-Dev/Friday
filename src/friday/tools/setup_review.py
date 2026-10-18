"""Outil du mode trading : le bilan du carnet des setups (P3). « Bilan des setups », « l'avis
de Claude aide-t-il ? » : ce que les setups FERMÉS auraient donné, tous ensemble, puis ceux
où Claude a dit oui et ceux où il a dit non. C'est la preuve à réunir avant de laisser Friday
trader : si les « oui » ne font pas mieux que tous les setups, l'avis de Claude n'aide pas."""

from friday.tools.base import Display, Tool, ToolResult
from friday.trading.alerts.review import review
from friday.trading.backtest.report import FEW, r_text


class SetupReviewTool(Tool):
    name = "setup_review"
    description = (
        "Bilan du carnet des setups : ce que les setups auraient donné, et si l'avis de Claude "
        "aide (« bilan des setups », « l'avis de Claude aide-t-il ? »)."
    )
    parameters = {}

    def __init__(self, watcher) -> None:
        self.watcher = watcher

    def label(self, args: dict) -> str:
        return "📒 Bilan des setups"

    def run(self) -> ToolResult:
        entries = self.watcher.setups.all()
        reports, running = review(entries)
        if not reports[0].count:
            return ToolResult(f"Dis EXACTEMENT : « Aucun setup terminé pour l'instant "
                              f"({len(entries)} noté(s), encore en cours). Il faut attendre que "
                              "les trades se ferment. »")  # fmt: skip
        whole, yes, no = reports[0], reports[1], reports[2]
        spoken = f"Sur {whole.count} setups terminés : {r_text(whole.expectancy)} par trade"
        if yes.count and no.count:
            spoken += (f" ; quand Claude dit oui, {r_text(yes.expectancy)} sur {yes.count} ; "
                       f"quand il dit non, {r_text(no.expectancy)} sur {no.count}")  # fmt: skip
            better = yes.expectancy - (whole.expectancy or 0)
            if whole.count < FEW:
                spoken += f". Moins de {FEW} setups : trop tôt pour conclure"
            elif better > max(yes.margin or 0, whole.margin or 0):
                spoken += ". Son avis améliore les résultats, au-delà du hasard"
            else:
                spoken += ". Pour l'instant, son avis ne fait pas nettement mieux"
        elif whole.count < FEW:
            spoken += f". Moins de {FEW} setups : trop tôt pour conclure"
        spoken += f" ; {running} encore en cours." if running else "."
        items = [{"text": r.label, "meta": r.summary()} for r in reports if r.count]
        return ToolResult(
            f"Dis EXACTEMENT : « {spoken} » Le détail est affiché.",
            Display("items", "Bilan des setups", {"icon": "📒", "items": items}),
        )
