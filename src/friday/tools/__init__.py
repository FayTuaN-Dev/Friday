"""Outils de Friday. Pour en ajouter un : créer un fichier ici et l'inscrire ci-dessous."""

from friday.core.config import Settings
from friday.tools.base import Display, Tool, ToolBox, ToolResult


def lab_tools(settings: Settings, on_background, holder: list) -> tuple[list[Tool], object]:
    """Atelier de compétences (J8). `holder` recevra la boîte à outils une fois créée : les
    compétences installées y sont ajoutées à chaud, ou retirées."""
    from friday.core.config import DATA_DIR
    from friday.skills_lab.lab import Lab
    from friday.tools.skills_lab import (
        CreateSkillTool,
        InstallSkillTool,
        ListLearnedSkillsTool,
        RemoveLearnedSkillTool,
    )

    lab = Lab(DATA_DIR)

    def install(tools: list[Tool]) -> None:
        for tool in tools:
            holder[0].add(tool)

    def remove(names: list[str]) -> None:
        for name in names:
            holder[0].remove(name)

    tools = [CreateSkillTool(lab, settings.claude_model, settings.claude_timeout, on_background),
             InstallSkillTool(lab, install), ListLearnedSkillsTool(lab),
             RemoveLearnedSkillTool(lab, remove)]  # fmt: skip
    return tools, lab


def routine_tools() -> list[Tool]:
    from friday.agenda.routines import RoutineStore
    from friday.core.config import DATA_DIR
    from friday.tools.routines import AddRoutineTool, ListRoutinesTool, RemoveRoutineTool

    store = RoutineStore(DATA_DIR / "routines.json")
    return [AddRoutineTool(store), ListRoutinesTool(store), RemoveRoutineTool(store)]


def default_toolbox(
    settings: Settings,
    memory=None,
    on_background=None,
    agenda=None,
    briefing=None,
    google=None,
    research=None,
    library=None,
    trading=None,
    day_log=None,
    world=None,
) -> ToolBox:
    """`on_background(tâche, résultat)` : appelé quand une tâche de fond (Claude) se termine.
    `research` : carnet de recherche (ResearchLog) partagé par la recherche et la lecture web."""
    tools: list[Tool] = []
    holder: list[ToolBox] = []  # la boîte à outils, pour l'atelier (J8)
    lab = None
    if settings.tools_enabled:
        from friday.tools.images import ImageSearchTool
        from friday.tools.markets import MarketQuoteTool
        from friday.tools.place import ShowPlaceTool
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
            MarketQuoteTool(),
            ShowPlaceTool(),
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

        tools += pc_tools(settings)
    if settings.claude_enabled and on_background is not None:
        from friday.tools.claude_code import CancelClaudeTool, ClaudeCodeJob, ClaudeCodeTool

        job = ClaudeCodeJob(
            settings.claude_workspace, settings.claude_model, settings.claude_timeout
        )
        claude = ClaudeCodeTool(job, on_background)
        workshop, lab = lab_tools(settings, on_background, holder)
        tools += [claude, CancelClaudeTool(job), *workshop]
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
    if trading is not None and on_background is not None:
        from friday.core.config import DATA_DIR
        from friday.tools.backtest import BacktestTool
        from friday.tools.trade_check import TradeCheckTool
        from friday.tools.trading import PipValueTool, PositionSizeTool, RiskRewardTool
        from friday.tools.trading_analysis import TradingAnalysisTool
        from friday.tools.trading_journal import (
            AnnotateTradeTool,
            CloseTradeTool,
            LogTradeTool,
            OpenJournalTool,
            TradeStatsTool,
        )

        account = trading.account_currency
        tools += [
            PositionSizeTool(account), PipValueTool(account), RiskRewardTool(),
            LogTradeTool(trading.journal, trading.entry_capture, DATA_DIR / "journal_captures"),
            AnnotateTradeTool(trading.journal), CloseTradeTool(trading.journal),
            TradeStatsTool(trading.journal), OpenJournalTool(), TradeCheckTool(trading),
            BacktestTool(trading),
        ]  # fmt: skip
        if trading.job is not None:  # l'analyse par Claude (mode trading)
            tools.append(TradingAnalysisTool(trading.builder, trading.job, trading.journal,
                                             on_background, trading.instrument_for,
                                             trading.chart_shows))  # fmt: skip
        from friday.tools.analyses import PastAnalysesTool
        from friday.trading.alerts.watcher import yahoo_price

        tools.append(PastAnalysesTool(trading.journal, yahoo_price))
        if trading.choice is not None:
            from friday.tools.strategies import (
                ChooseStrategyTool,
                CompareStrategiesTool,
                StrategyLab,
            )

            strategies = StrategyLab(trading)
            tools += [CompareStrategiesTool(strategies, trading.choice),
                      ChooseStrategyTool(strategies, trading.choice)]  # fmt: skip
        if trading.translator is not None and trading.choice is not None:
            from friday.tools.plan_translate import TranslatePlanTool

            tools.append(TranslatePlanTool(trading.choice, trading.translator, trading.journal,
                                           on_background, settings.trading.blocklist))  # fmt: skip
        if trading.briefing is not None:
            from friday.tools.trading_briefing import TradingBriefingTool

            tools.append(TradingBriefingTool(trading.briefing))
        if trading.alerts is not None:
            from friday.tools.alerts import (
                CancelAlertTool,
                ListAlertsTool,
                PriceAlertTool,
                WatchSetupTool,
            )

            tools += [PriceAlertTool(trading.alerts), WatchSetupTool(trading.alerts),
                      ListAlertsTool(trading.alerts), CancelAlertTool(trading.alerts)]  # fmt: skip
    if library is not None:
        from friday.tools.library import ListLibraryTool, SearchLibraryTool, UpdateLibraryTool

        tools += [SearchLibraryTool(library), ListLibraryTool(library), UpdateLibraryTool(library)]
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
            *routine_tools(),
        ]  # fmt: skip
    if memory is not None:
        from friday.tools.memory import ForgetTool, ListMemoriesTool, RememberTool
        from friday.tools.memory_origin import MemoryOriginTool
        from friday.tools.memory_sheet import OpenMemorySheetTool

        tools += [RememberTool(memory), ForgetTool(memory), ListMemoriesTool(memory),
                  MemoryOriginTool(memory), OpenMemorySheetTool(memory)]  # fmt: skip
        if settings.night_dream:
            from friday.core.config import DATA_DIR
            from friday.tools.dream_report import DreamReportTool

            tools.append(DreamReportTool(DATA_DIR / "reve"))
    if day_log is not None:
        from friday.tools.day_memory import RecallDayTool

        tools.append(RecallDayTool(day_log))
    if world is not None:  # veille monde (J9) ; les marchés : briefing trading, alertes
        from friday.tools.world import (
            MarketMoversTool,
            ShowWorldTool,
            WorldNewsTool,
            my_instruments,
        )

        def mine():
            return my_instruments(trading)

        tools += [WorldNewsTool(world), MarketMoversTool(world, mine), ShowWorldTool(world, mine)]
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
    box = ToolBox(tools)
    holder.append(box)
    if lab is not None:  # les compétences apprises (ré-inspectées à chaque chargement)
        for _, _, learned in lab.load_all():
            for tool in learned:
                box.add(tool)
    return box


__all__ = ["Display", "Tool", "ToolBox", "ToolResult", "default_toolbox"]
