"""Outils de Jarvis. Pour en ajouter un : créer un fichier ici et l'inscrire ci-dessous."""

from jarvis.core.config import Settings
from jarvis.tools.base import Display, Tool, ToolBox, ToolResult


def default_toolbox(settings: Settings) -> ToolBox:
    if not settings.tools_enabled:
        return ToolBox([])

    from jarvis.tools.images import ImageSearchTool
    from jarvis.tools.web_page import ReadWebPageTool
    from jarvis.tools.web_search import WebSearchTool

    return ToolBox(
        [
            WebSearchTool(settings.search_region),
            ReadWebPageTool(),
            ImageSearchTool(settings.search_region),
        ]
    )


__all__ = ["Display", "Tool", "ToolBox", "ToolResult", "default_toolbox"]
