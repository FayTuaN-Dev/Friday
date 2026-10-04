"""Outils de Jarvis. Pour en ajouter un : créer un fichier ici et l'inscrire ci-dessous."""

from jarvis.core.config import Settings
from jarvis.tools.base import Display, Tool, ToolBox, ToolResult


def default_toolbox(settings: Settings, memory=None, on_background=None, agenda=None) -> ToolBox:
    """`on_background(tâche, résultat)` : appelé quand une tâche de fond (Claude) se termine."""
    tools: list[Tool] = []
    if settings.tools_enabled:
        from jarvis.tools.images import ImageSearchTool
        from jarvis.tools.weather import WeatherTool
        from jarvis.tools.web_page import ReadWebPageTool
        from jarvis.tools.web_search import WebSearchTool

        tools += [
            WeatherTool(settings.home_city),
            WebSearchTool(settings.search_region, backend=settings.search_backend),
            ReadWebPageTool(),
            ImageSearchTool(settings.search_region),
        ]
    if settings.pc_control:
        from jarvis.tools.pc import pc_tools

        tools += pc_tools()
    if settings.claude_enabled and on_background is not None:
        from jarvis.tools.claude_code import CancelClaudeTool, ClaudeCodeJob, ClaudeCodeTool

        job = ClaudeCodeJob(
            settings.claude_workspace, settings.claude_model, settings.claude_timeout
        )
        tools += [ClaudeCodeTool(job, on_background), CancelClaudeTool(job)]
    if agenda is not None:
        from jarvis.tools.notes import AddNoteTool, ListNotesTool, RemoveNoteTool
        from jarvis.tools.reminders import (
            CancelReminderTool,
            ListRemindersTool,
            SetReminderTool,
            SetTimerTool,
        )

        tools += [
            SetTimerTool(agenda), SetReminderTool(agenda), ListRemindersTool(agenda),
            CancelReminderTool(agenda), AddNoteTool(agenda), ListNotesTool(agenda),
            RemoveNoteTool(agenda),
        ]  # fmt: skip
    if memory is not None:
        from jarvis.tools.memory import ForgetTool, ListMemoriesTool, RememberTool

        tools += [RememberTool(memory), ForgetTool(memory), ListMemoriesTool(memory)]
    return ToolBox(tools)


__all__ = ["Display", "Tool", "ToolBox", "ToolResult", "default_toolbox"]
