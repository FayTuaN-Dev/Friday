"""Ce que Friday prépare d'office avant de répondre : les consignes par demande (hints) et
l'outil lancé d'avance (prefetch) — bibliothèque, ou analyse en mode trading."""

from friday.trading.mode import briefing_request, strategy_request

TRADING_LOCAL = (
    "Mode trading : demande locale (calcul de risque, journal…) : utilise les outils du PC, "
    "rien ne part en ligne."
)


def hints(library, trading) -> dict:
    """Consignes par demande : la bibliothèque si elle connaît le sujet (hors mode trading),
    la compétence trading pour les demandes locales du mode trading."""
    found = {}
    if library:
        found["library"] = lambda text: (
            "" if trading and trading.mode.enabled else library.hint(text)
        )
    if trading:
        found["trading"] = lambda text: TRADING_LOCAL if trading.mode.enabled else ""
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
    library, trading, router, mail: bool = False, days: bool = False, memory: bool = False
):
    """Outil lancé d'office avant de répondre. Mode trading : une question d'analyse part dans
    le paquet pour Claude (après aperçu). Sinon : la bibliothèque, si elle connaît le sujet."""
    choose = router.choose if router else None

    def prefetch(text: str) -> tuple[str, dict] | None:
        if memory:
            from friday.tools.memory_origin import asked_origin

            if about := asked_origin(text):  # « d'où tu sais que… » : trouvé par le code
                return ("memory_origin", {"about": about})
        if days:
            from friday.memory.day_log import asks_day

            if asks_day(text):  # « de quoi on a parlé hier ? » : le jour, calculé par le code
                return ("recall_day", {"day": text})
        if mail:
            from friday.tools.mail_sorting import asks_categories

            if asks_categories(text):  # la liste, lue par le code (le modèle se trompait)
                return ("category_mails", {})
        if trading and trading.mode.enabled:
            if getattr(trading, "choice", None) is not None and (
                    asked := plan_request(text, trading.choice.book)):  # fmt: skip
                return asked  # le code choisit l'outil, l'instrument, la stratégie, le plan
            if trading.briefing is not None and (wanted := briefing_request(text)) is not None:
                return ("trading_briefing", {"instrument": wanted})  # le code choisit
            if trading.mode.route(text, choose) == "analysis":
                return ("trading_analysis", {"question": text})
            return None
        return library.auto_search(text) if library else None

    return prefetch
