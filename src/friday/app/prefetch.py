"""Ce que Friday prépare d'office avant de répondre : les consignes par demande (hints) et
l'outil lancé d'avance (prefetch) — bibliothèque, ou analyse en mode trading."""

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


def prefetcher(library, trading, router):
    """Outil lancé d'office avant de répondre. Mode trading : une question d'analyse part dans
    le paquet pour Claude (après aperçu). Sinon : la bibliothèque, si elle connaît le sujet."""
    choose = router.choose if router else None

    def prefetch(text: str) -> tuple[str, dict] | None:
        if trading and trading.mode.enabled:
            if trading.mode.route(text, choose) == "analysis":
                return ("trading_analysis", {"question": text})
            return None
        return library.auto_search(text) if library else None

    return prefetch
