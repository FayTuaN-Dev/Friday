"""Outils de Friday. Pour en ajouter un : créer un fichier ici et l'inscrire ci-dessous."""

from friday.core.config import Settings
from friday.tools.base import Display, Tool, ToolBox, ToolResult


def default_toolbox(
    settings: Settings,
    memory=None,
    on_background=None,
    agenda=None,
    briefing=None,
    google=None,
    research=None,
) -> ToolBox:
    """`on_background(tâche, résultat)` : appelé quand une tâche de fond (Claude) se termine.
    `research` : carnet de recherche (ResearchLog) partagé par la recherche et la lecture web."""
    tools: list[Tool] = []
    if settings.tools_enabled:
        from friday.tools.images import ImageSearchTool
        from friday.tools.weather import WeatherTool
        from friday.tools.web_page import ReadWebPageTool
        from friday.tools.web_search import WebSearchTool

        tools += [
            WeatherTool(settings.home_city),
            WebSearchTool(
                settings.search_region, backend=settings.search_backend, research=research
            ),
            ReadWebPageTool(research),
            ImageSearchTool(settings.search_region),
        ]
    if settings.files_access:
        from friday.files.folders import search_folders
        from friday.files.search import FileFinder
        from friday.tools.file_search import OpenFileTool, SearchFilesTool
        from friday.tools.files import CopyToClipboardTool, ReadClipboardTool, ReadFileTool

        tools += [
            ReadFileTool(), ReadClipboardTool(), CopyToClipboardTool(),
            SearchFilesTool(FileFinder(search_folders())), OpenFileTool(),
        ]  # fmt: skip
    if settings.pc_control:
        from friday.tools.pc import pc_tools

        tools += pc_tools()
    if settings.claude_enabled and on_background is not None:
        from friday.tools.claude_code import CancelClaudeTool, ClaudeCodeJob, ClaudeCodeTool

        job = ClaudeCodeJob(
            settings.claude_workspace, settings.claude_model, settings.claude_timeout
        )
        claude = ClaudeCodeTool(job, on_background)
        tools += [claude, CancelClaudeTool(job)]
    else:
        claude = None
    if settings.vision_enabled:
        import ollama

        from friday.tools.screen import AskClaudeAboutScreenTool, LookAtScreenTool
        from friday.vision.capture import capture_screen
        from friday.vision.reader import ScreenReader

        reader = ScreenReader(ollama.Client(host=settings.ollama_host), settings.vision_model)
        tools.append(LookAtScreenTool(reader, capture_screen))
        if claude is not None:  # secours, avec confirmation
            tools.append(AskClaudeAboutScreenTool(claude, capture_screen))
    if agenda is not None:
        from friday.tools.notes import AddNoteTool, ListNotesTool, RemoveNoteTool
        from friday.tools.reminders import (
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
        from friday.tools.memory import ForgetTool, ListMemoriesTool, RememberTool

        tools += [RememberTool(memory), ForgetTool(memory), ListMemoriesTool(memory)]
    if google is not None:
        from friday.tools.google_tools import google_tools

        tools += google_tools(google, settings, on_background)
    if briefing is not None:
        from friday.tools.briefing import (
            ConfigureBriefingTool,
            MorningBriefingTool,
            ShowBriefingSettingsTool,
        )

        configure = ConfigureBriefingTool(briefing)
        tools += [MorningBriefingTool(briefing), configure, ShowBriefingSettingsTool(configure)]
    if tools:  # fermer les pop-ups ouverts par les autres outils
        from friday.tools.popups import ClosePopupsTool, OpenSettingsTool

        tools += [ClosePopupsTool(), OpenSettingsTool()]
    return ToolBox(tools)


__all__ = ["Display", "Tool", "ToolBox", "ToolResult", "default_toolbox"]
