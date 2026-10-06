"""Outils : faire le briefing du matin sur demande, et le configurer à la voix."""

from dataclasses import replace
from datetime import datetime

from friday.briefing import Briefing
from friday.briefing.config import KINDS
from friday.tools.base import Display, Tool, ToolResult


class MorningBriefingTool(Tool):
    name = "morning_briefing"
    description = (
        "DIT le briefing du matin à voix haute (météo, actualités… selon les rubriques) : "
        "« fais-moi mon briefing », « quoi de neuf aujourd'hui ? ». Pas pour afficher ou "
        "modifier ses rubriques : c'est show_briefing_settings / configure_briefing."
    )
    parameters: dict = {}
    timeout = 30  # météo et actualités en ligne

    def __init__(self, briefing: Briefing) -> None:
        self.briefing = briefing

    def label(self, args: dict) -> str:
        return "☀️ Briefing du matin"

    def run(self) -> ToolResult:
        now = datetime.now()
        facts = self.briefing.facts(now)
        self.briefing.mark_done(now)  # pas de second briefing automatique aujourd'hui
        if not facts:
            return ToolResult(
                "Le briefing est vide aujourd'hui (rien à signaler). Dis-le en une phrase."
            )
        return ToolResult(
            f"Informations du briefing, rubrique par rubrique :\n\n{facts}\n\nPrésente-les en "
            "quelques phrases, dans l'ordre, sans liste. N'invente rien et n'ajoute rien."
        )


class ShowBriefingSettingsTool(Tool):
    name = "show_briefing_settings"
    description = (
        "AFFICHE dans une fenêtre les rubriques du briefing (ce qu'il contient, ce que Friday "
        "surveille le matin), pour les vérifier, modifier ou retirer : « montre ce qu'il y a "
        "dans mon briefing », « affiche les rubriques du brief », « qu'est-ce que tu regardes "
        "le matin ? ». Ne dit PAS le briefing."
    )
    parameters: dict = {}

    def __init__(self, configure: "ConfigureBriefingTool") -> None:
        self.configure = configure

    def label(self, args: dict) -> str:
        return "☀️ Rubriques du briefing"

    def run(self) -> ToolResult:
        result = self.configure.run("list")
        return ToolResult(
            f"{result.text} Elles sont affichées : cite-les brièvement et propose de les "
            "modifier ou d'en retirer.",
            result.display,
        )


class ConfigureBriefingTool(Tool):
    name = "configure_briefing"
    description = (
        "Règle le briefing du matin : ajouter ou retirer une rubrique, voir les rubriques "
        "(action list : « qu'y a-t-il dans mon briefing ? »), activer ou désactiver le briefing "
        "automatique. Rubriques : meteo (value = ville, si l'utilisateur la donne), agenda "
        "(agenda Google du jour), mails (non lus), rappels "
        "(du jour), "
        "liste (contenu d'une liste : value = nom de la liste), actualites (value = sujet), "
        "libre (value = consigne, ex. « un conseil sport », « une citation »)."
    )
    parameters = {
        "action": {"type": "string", "enum": ["add", "remove", "list", "enable", "disable"]},
        "kind": {"type": "string", "enum": list(KINDS), "description": "Type de rubrique"},
        "value": {"type": "string", "description": "Liste, sujet ou consigne de la rubrique"},
    }
    required = ("action",)

    def __init__(self, briefing: Briefing) -> None:
        self.briefing = briefing

    def label(self, args: dict) -> str:
        return f"☀️ Réglage du briefing : {args.get('action', '')} {args.get('value', '')}".strip()

    def run(self, action: str, kind: str = "", value: str = "") -> ToolResult:
        if action in ("enable", "disable"):
            self.briefing.set_enabled(action == "enable")
            state = "activé" if action == "enable" else "désactivé"
            return self._refreshed(f"Briefing automatique du matin {state}.")
        if action == "add":
            return self._refreshed(self.briefing.add(kind, value))
        if action == "remove":
            return self._refreshed(self.briefing.remove(kind, value))
        return self._listing()

    def _refreshed(self, text: str) -> ToolResult:
        """Le changement est fait ; la pop-up des rubriques, si elle est ouverte, suit."""
        return ToolResult(text, replace(self._listing().display, refresh=True))

    def _listing(self) -> ToolResult:
        config = self.briefing.config
        city_known = self.briefing.sources_city_known()
        items = [
            {
                "text": s.label()
                + ("" if s.kind != "meteo" or s.value or city_known else " (ville à préciser)")
            }  # fmt: skip
            for s in config.sections
        ]
        state = "activé" if config.enabled else "désactivé"
        hours = f"de {config.start_hour} h à {config.end_hour} h"
        summary = ", ".join(i["text"] for i in items) or "aucune rubrique"
        return ToolResult(
            f"Briefing {state} (au premier démarrage {hours}). Rubriques : {summary}.",
            Display(
                "items",
                f"Briefing du matin ({state})",
                {"icon": "☀️", "items": items},
                key="briefing",
            ),  # fmt: skip
        )
