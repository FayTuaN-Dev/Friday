"""Outil : fermer les pop-ups que Friday a ouverts (résultats, météo, fichiers…)."""

from friday.tools.base import Display, Tool, ToolResult

CLOSE = "close"  # type de Display spécial : l'interface ferme des pop-ups au lieu d'en ouvrir


class OpenSettingsTool(Tool):
    name = "open_settings"
    description = (
        "Ouvre la fenêtre des réglages de Friday (voix, micro, couleur, briefing, fonctions, "
        "compte Google) : « ouvre les réglages », « les paramètres »."
    )
    parameters: dict = {}

    def label(self, args: dict) -> str:
        return "⚙️ Réglages"

    def run(self) -> ToolResult:
        return ToolResult(
            "Réglages ouverts. Dis-le en une phrase.", Display("settings", "Réglages")
        )


class ClosePopupsTool(Tool):
    name = "close_popups"
    description = (
        "Ferme les fenêtres que TU as affichées à l'écran (résultats, articles, images, météo, "
        "fichiers trouvés, listes…). Pas pour les applications : c'est close_app."
    )
    parameters = {
        "which": {
            "type": "string",
            "enum": ["all", "last"],
            "description": "all : toutes (par défaut) ; last : seulement la dernière ouverte",
        }
    }

    def label(self, args: dict) -> str:
        return "🗙 Fermeture des fenêtres affichées"

    def run(self, which: str = "all") -> ToolResult:
        which = "last" if which == "last" else "all"
        return ToolResult(
            "Fenêtres fermées. Confirme en quelques mots.", Display(CLOSE, "", {"which": which})
        )
