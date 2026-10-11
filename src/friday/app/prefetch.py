"""Ce que Friday prépare d'office avant de répondre : les consignes par demande (hints) et
l'outil lancé d'avance (prefetch) — bibliothèque, ou analyse en mode trading."""

from friday.trading.mode import ASK_ANALYSIS, briefing_request, strategy_request

TRADING_LOCAL = (
    "Mode trading : demande locale (calcul de risque, journal…) : utilise les outils du PC, "
    "rien ne part en ligne."
)
TRADING_ANALYSIS = "Mode trading actif : une question d'analyse de marché → trading_analysis."
# Hors mode trading : un instrument (« l'or », « EUR/USD ») + un de ces mots → les outils
MARKET_WORDS = ("alerte", "previens", "surveille", "achet", "achat", "vend", "vente", "stop",
                "short", "backtest", "teste", "briefing", "strategie", "setup", "lots",
                "pips")  # fmt: skip


def pip_request(text: str) -> tuple[str, dict] | None:
    """« combien vaut un pip sur 2 lots d'or » → pip_value, choisi par le code : qwen
    demandait le cours au lieu de calculer, une fois sur deux (constaté, T8)."""
    import re

    from friday.trading.instruments import detect
    from friday.voice.wake import normalize

    if not re.search(r"\bpips?\b", normalize(text)):
        return None
    lots = re.search(r"(\d+(?:[.,]\d+)?)\s*lots?\b", text)
    found = detect(re.sub(r"\b[dD](?:'|’| )or\b", "l'or", text))  # « 2 lots d'or »
    if lots is None or found is None:
        return None
    return ("pip_value", {"instrument": found.name, "lots": float(lots.group(1).replace(",", "."))})


def market_request(text: str) -> str:
    """« préviens-moi si l'or passe 4 150 » : la consigne qui active les outils de trading."""
    from friday.trading.instruments import detect
    from friday.voice.wake import normalize

    padded = f" {normalize(text)} "
    found = detect(text)
    if found is None:
        return ""
    if any(f" {w}" in padded for w in ASK_ANALYSIS):
        return (f"Question d'analyse sur {found.name} : seul Claude l'analyse, en mode trading ; "
                "propose de dire « mode trading ».")  # fmt: skip
    if any(f" {w}" in padded for w in MARKET_WORDS):
        return f"Demande de trading ({found.name}) : outils de trading du PC."
    return ""


def hints(library, trading) -> dict:
    """Consignes par demande : la bibliothèque si elle connaît le sujet (hors mode trading) ;
    les outils de trading en mode trading, ou hors mode pour une demande sur un instrument ;
    l'analyse par Claude en mode trading."""
    found = {}
    if library:
        found["library"] = lambda text: (
            "" if trading and trading.mode.enabled else library.hint(text)
        )
    if trading:
        found["trading"] = lambda text: (
            TRADING_LOCAL if trading.mode.enabled else market_request(text)
        )
        found["analyse_trading"] = lambda text: TRADING_ANALYSIS if trading.mode.enabled else ""
    return found


def plan_request(text: str, book) -> tuple[str, dict] | None:
    """Les demandes sur les stratégies et les plans écrits, reconnues par le code ; avec le
    plan nommé dans la phrase (« teste le plan Cassure Londres sur l'or »)."""
    from friday.trading.instruments import detect
    from friday.voice.wake import normalize

    asked = strategy_request(text)
    if asked is not None:
        tool, args = asked
        if tool in ("translate_plan", "choose_strategy"):
            args = {**args, "request": text}
        return tool, args
    plan = book.find(text)
    words = f" {normalize(text)} "
    if plan and any(f" {w}" in words for w in ("teste", "tester", "backtest", "back test")):
        found = detect(text.replace(plan["nom"], ""))
        return ("backtest_plan", {"instrument": found.symbol if found else "", "plan": plan["id"]})
    return None


def prefetcher(
    library,
    trading,
    router,
    mail: bool = False,
    days: bool = False,
    memory: bool = False,
    world: bool = False,
    music: bool = False,
):
    """Outil lancé d'office avant de répondre. Plans, stratégies et briefing trading : choisis
    par le code. Mode trading : une question d'analyse part dans le paquet pour Claude (après
    aperçu). Sinon : la bibliothèque, si elle connaît le sujet."""
    choose = router.choose if router else None

    def prefetch(text: str) -> tuple[str, dict] | None:
        if memory:
            from friday.tools.memory_origin import asked_origin

            if about := asked_origin(text):  # « d'où tu sais que… » : trouvé par le code
                return ("memory_origin", {"about": about})
            from friday.tools.dream_report import asks_dream

            if asks_dream(text):  # « qu'as-tu fait cette nuit ? »
                return ("dream_report", {})
            from friday.tools.memory_sheet import asks_sheet

            if asks_sheet(text):  # « ouvre ta fiche mémoire » (qwen ouvrait le Bloc-notes vide)
                return ("open_memory_sheet", {})
        if days:
            from friday.memory.day_log import asks_day

            if asks_day(text):  # « de quoi on a parlé hier ? » : le jour, calculé par le code
                return ("recall_day", {"day": text})
        if mail:
            from friday.tools.mail_sorting import asks_categories

            if asks_categories(text):  # la liste, lue par le code (le modèle se trompait)
                return ("category_mails", {})
            from friday.tools.mail_trash import trash_request

            if asked := trash_request(text):  # un expéditeur, pas des catégories devinées
                return asked
        if music:
            from friday.spotify.matching import music_request

            if asked := music_request(text):  # « mets un peu d'électro » : vraiment lancé
                return asked
        if world:
            from friday.tools.world import world_request

            if asked := world_request(text):  # l'outil et l'instrument : choisis par le code
                return asked
        if trading:  # avec ou sans mode trading (une routine « briefing trading » aussi)
            if asked := pip_request(text):
                return asked
            if getattr(trading, "choice", None) is not None and (
                    asked := plan_request(text, trading.choice.book)):  # fmt: skip
                return asked  # le code choisit l'outil, l'instrument, la stratégie, le plan
            wanted = briefing_request(text, strict=not trading.mode.enabled)
            if trading.briefing is not None and wanted is not None:
                return ("trading_briefing", {"instrument": wanted})  # le code choisit
        if trading and trading.mode.enabled:
            if trading.job is not None and trading.mode.route(text, choose) == "analysis":
                return ("trading_analysis", {"question": text})
            return None
        return library.auto_search(text) if library else None

    return prefetch
