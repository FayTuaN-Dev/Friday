"""Chargement des briques facultatives : compte Google, briefing du matin."""

import logging

from friday.core.config import DATA_DIR, Settings

log = logging.getLogger(__name__)


def load_google(settings: Settings):
    """Compte Google, si le client OAuth est installé ; la 1re fois, ouvre l'autorisation."""
    if not settings.google_enabled:
        return None
    from friday.google import GoogleAccount

    account = GoogleAccount(DATA_DIR / "google_credentials.json", DATA_DIR / "google_token.json")
    if not account.configured:
        return None
    if not account.connected:
        log.info("Compte Google à autoriser : ouverture du navigateur")
        account.connect_in_background()
    return account


def load_briefing(settings: Settings, agenda, google=None):
    """Briefing du matin : ses rubriques puisent dans la météo, l'agenda et l'actualité."""
    from friday.briefing import Briefing, Sources

    sources = Sources(agenda=agenda)
    if google is not None:
        from friday.google.sources import calendar_lines, unread_lines

        sources.calendar = lambda day: calendar_lines(google, day)
        sources.mail = lambda: unread_lines(google)
    if settings.tools_enabled:
        from ddgs import DDGS

        from friday.tools.base import retry
        from friday.tools.weather import WeatherTool

        def weather(city: str) -> str | None:
            city = city or settings.home_city
            return WeatherTool(city).run().text if city else None  # sans ville : rien

        def news(topic: str) -> list[str]:
            region = settings.search_region
            try:
                hits = retry(lambda: DDGS().news(topic, region=region, timelimit="d",
                                                 max_results=6))  # fmt: skip
                return [f"{h['title']} ({h.get('source', '')})" for h in hits or []]
            except Exception as error:  # service d'actualités saturé : recherche classique
                log.info("Actualités indisponibles (%s), repli sur la recherche web", error)
                hits = DDGS().text(f"actualité {topic}", region=region, timelimit="d",
                                   max_results=6)  # fmt: skip
                return [h["title"] for h in hits or []]

        sources.weather, sources.news = weather, news
    return Briefing(DATA_DIR / "briefing.json", sources, settings.home_city)


def load_library(settings: Settings, memory):
    """Bibliothèque de documents (data/bibliotheque), indexée en arrière-plan au démarrage.
    Elle utilise le modèle d'embeddings de la mémoire : sans mémoire, pas de bibliothèque."""
    if not settings.library_enabled or memory is None:
        return None
    try:
        from friday.library.library import Library
        from friday.library.store import LibraryStore

        library = Library(
            DATA_DIR / "bibliotheque", LibraryStore(DATA_DIR / "library.db"), memory.embedder
        )
        library.sync_in_background()
        return library
    except Exception:
        log.exception("Bibliothèque indisponible, Friday continue sans")
        return None


def load_trading(settings: Settings, library):
    """Mode trading (désactivé au démarrage, activé par « mode trading »). Demande Claude Code."""
    if not settings.trading.enabled or not settings.claude_enabled:
        return None
    try:
        from friday.trading import Trading, news, related
        from friday.trading.alerts.store import AlertStore
        from friday.trading.alerts.watcher import AlertWatcher
        from friday.trading.analyst import isolated_job
        from friday.trading.briefing_service import BriefingService
        from friday.trading.capture import ChartCapture
        from friday.trading.context_builder import ContextBuilder
        from friday.trading.context_sources import ContextSources
        from friday.trading.fred import FredResults
        from friday.trading.journal import TradeJournal
        from friday.trading.market import snapshot
        from friday.trading.mode import TradingMode
        from friday.trading.strategy_choice import StrategyChoice
        from friday.trading.warm import Warm

        config = settings.trading
        DATA_DIR.mkdir(exist_ok=True)
        journal = TradeJournal(DATA_DIR / "trading.db")
        capture = ChartCapture(config.capture_window, DATA_DIR / "trading.json")
        result = FredResults(config.fred_key, DATA_DIR / "cache") if config.fred_key else None
        warm = Warm()  # données publiques préparées en avance (trading/warm.py)
        context = ContextSources(DATA_DIR / "trading_plan.txt", DATA_DIR / "cache",
                                 hours=config.hours, result=result,
                                 headlines=warm.wrap("actualites", news.fetch_headlines),
                                 quote=warm.wrap("cours", related.yahoo_quote))  # fmt: skip
        market = warm.wrap("marche", snapshot)
        builder = ContextBuilder(library, journal, config.passages, config.max_chars,
                                 config.blocklist, capture, market, context)  # fmt: skip
        job = isolated_job(DATA_DIR / "trading_claude", config.model or settings.claude_model,
                           settings.claude_timeout)  # fmt: skip
        rules = DATA_DIR / "trading_rules.json"
        alerts = AlertWatcher(AlertStore(DATA_DIR / "trading_alerts.json"), rules,
                              capture.window_title, hours=config.hours)  # fmt: skip
        trading = Trading(TradingMode(), journal, builder, job, config.account_currency, capture,
                          rules_path=rules, alerts=alerts)  # fmt: skip
        trading.briefing = BriefingService(trading, DATA_DIR / "trading_briefing.json",
                                           config.hours, config.briefing_instruments,
                                           config.briefing)  # fmt: skip
        trading.prepare = lambda instrument: (market(instrument), context.blocks(instrument))
        trading.choice = StrategyChoice(DATA_DIR / "trading_strategies.json")
        alerts.choice = trading.choice  # les alertes suivent la stratégie choisie
        return trading
    except Exception:
        log.exception("Mode trading indisponible, Friday continue sans")
        return None
