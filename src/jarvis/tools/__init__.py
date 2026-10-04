"""Outils de Jarvis. Pour en ajouter un : créer un fichier ici et l'inscrire ci-dessous."""

from jarvis.core.config import Settings
from jarvis.tools.base import Display, Tool, ToolBox, ToolResult


def default_toolbox(settings: Settings, memory=None) -> ToolBox:
    tools: list[Tool] = []
    if settings.tools_enabled:
        from jarvis.tools.images import ImageSearchTool
        from jarvis.tools.web_page import ReadWebPageTool
        from jarvis.tools.web_search import WebSearchTool

        tools += [
            WebSearchTool(settings.search_region, backend=settings.search_backend),
            ReadWebPageTool(),
            ImageSearchTool(settings.search_region),
        ]
    if memory is not None:
        from jarvis.tools.memory import ForgetTool, ListMemoriesTool, RememberTool

        tools += [RememberTool(memory), ForgetTool(memory), ListMemoriesTool(memory)]
    return ToolBox(tools)


__all__ = ["Display", "Tool", "ToolBox", "ToolResult", "default_toolbox"]
