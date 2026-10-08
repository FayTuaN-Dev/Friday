"""Mode trading : activé / désactivé à la voix ou au clavier (« mode trading », « fin du mode
trading »), reconnu par du code avant le modèle. Hors de ce mode, rien ne change.

En mode trading, l'aiguillage est déterministe :
- calculs de risque, journal, check-list d'une idée de trade (sens + prix + stop), et tout ce
  qui relève d'une autre compétence (mails, PC…)
  → le modèle local, comme d'habitude ;
- le reste (une question d'analyse) → le paquet pour Claude, toujours après aperçu.
"""

from collections.abc import Callable

from friday.voice.wake import normalize

ON = ("mode trading", "active le mode trading", "passe en mode trading", "lance le mode trading",
      "mode trading on", "on passe en mode trading")  # fmt: skip
OFF = ("fin du mode trading", "fin mode trading", "quitte le mode trading", "sors du mode trading",
       "desactive le mode trading", "arrete le mode trading", "stop mode trading",
       "termine le mode trading", "mode trading off")  # fmt: skip
PREFIXES = ("friday ", "ok ", "bon ", "allez ", "vas y ")
# Briefing trading (calculé sur le PC) : lancé d'office par le code (prefetch)
BRIEFING = ("briefing trading", "brief trading", "journee de trading", "prepare ma journee")
LOCAL = (
    # calculs de risque (déterministes, sur ce PC)
    "taille de position", "combien de lots", "nombre de lots", "combien de lot", "valeur du pip",
    "valeur d un pip", "ratio", "risque rendement", "risk reward", "perte max", "calcule",
    "combien je risque", "combien je perds",
    # journal (local)
    "journal", "mes trades", "note le trade", "enregistre le trade", "ajoute un trade",
    "nouveau trade", "cloture le trade", "ferme le trade", "mon bilan", "mes statistiques",
    "mes performances",
    # check-list avant trade (règles du plan vérifiées par le code)
    "check list", "checklist", "respecte mon plan", "respecte le plan", "respecte t il mon plan",
    "respecte t il le plan", "verifie mon trade", "verifie ce trade", "verifie mon idee",
    "feu vert",
    # backtest du plan (sur le PC)
    "backtest", "back test", "teste mon plan", "tester mon plan", "teste le plan",
    "sur l historique", "aurait gagne", "aurait perdu", "aurait il gagne", "aurait il perdu",
    "et avec un objectif", "et avec un stop", "et avec une variante",
    # alertes (surveillées sur le PC) et leurs annonces
    "alerte", "previens moi", "surveille", "setup se forme",
    # briefing trading (calculé sur le PC)
    *BRIEFING,
    # bibliothèque de stratégies (locale)
    "strategie", "strategies",
    # mémoire des analyses (locale)
    "mes analyses", "dernieres analyses", "tes analyses", "analyses passees",
)  # fmt: skip
# Une idée de trade chiffrée (« acheter l'or à 4 160, stop 4 140 ») : la check-list, en local.
DIRECTIONS = ("acheter", "achete", "achat", "vendre", "vends", "vend", "vente", "long", "short",
              "buy", "sell")  # fmt: skip
STOPS = ("stop", "sl")
# … sauf si l'utilisateur demande explicitement l'avis de Claude sur cette idée.
ASK_ANALYSIS = ("claude", "analyse", "analyser", "ton avis", "qu en penses", "que penses")
# Revue hebdomadaire du journal : par Claude (bilan anonyme, après aperçu), jamais locale.
REVIEW = ("revue", "bilan de la semaine", "bilan hebdo", "debrief de la semaine")
# Compétences qui ne concernent pas une analyse de trading : elles restent locales.
OTHER_SKILLS = {"pc", "mail", "calendar", "reminders", "files", "briefing", "claude"}


# La question parle du graphique affiché : capture ciblée (et seulement alors).
CHART = ("graphique", "graph", "chart", "bougie", "chandelier", "ce que je vois", "a l ecran",
         "sur l ecran", "mon ecran", "regarde", "cette figure", "ce motif", "ce pattern",
         "cette configuration", "la courbe", "ce setup", "mon setup")  # fmt: skip


def mentions_chart(text: str) -> bool:
    padded = f" {normalize(text)} "
    return any(f" {word}" in padded for word in CHART)


def _command_words(text: str) -> str:
    words = normalize(text)
    for prefix in PREFIXES:
        if words.startswith(prefix):
            words = words[len(prefix) :]
    return words.strip()


def briefing_request(text: str) -> str | None:
    """« briefing trading (sur l'argent) » → le symbole demandé, « » pour ceux des réglages,
    ou None. Choisi par le code : qwen passait toujours l'or, même pour l'argent (constaté).
    Les annonces automatiques (« (Message automatique… ») ne relancent rien."""
    if text.lstrip().startswith("(Message automatique"):
        return None
    padded = f" {normalize(text)} "
    if not any(f" {word}" in padded for word in BRIEFING):
        return None
    from friday.trading.instruments import detect

    found = detect(text)
    return found.symbol if found else ""


COMPARE = ("compare les strategies", "compare mes strategies", "quelle strategie",
           "quelles strategies", "meilleure strategie", "bibliotheque de strategies",
           "strategies qui marchent", "strategie qui marche")  # fmt: skip
CHOOSE = ("choisis", "prends", "adopte", "utilise", "passe a", "passe sur", "reviens a",
          "garde")  # fmt: skip


def strategy_request(text: str) -> tuple[str, dict] | None:
    """(outil, arguments) d'une demande sur les stratégies, choisis par le code ; ou None."""
    from friday.trading.instruments import detect
    from friday.trading.strategies import strategy_named

    if text.lstrip().startswith("(Message automatique"):
        return None
    padded = f" {normalize(text)} "
    found = detect(text)
    instrument = found.symbol if found else ""
    if any(f" {w}" in padded for w in COMPARE):
        everything = any(f" {w} " in padded for w in ("tous", "toutes", "chaque"))
        return ("compare_strategies", {"instrument": "" if everything else instrument,
                                       "everything": everything and not found})  # fmt: skip
    name = strategy_named(text)
    plan = " mon plan" in padded or " ton plan" in padded or "strategie" in padded
    if name and any(f" {w} " in padded for w in CHOOSE) and (plan or name != "plan"):
        return ("choose_strategy", {"strategy": name, "instrument": instrument})
    return None


def is_review(text: str) -> bool:
    padded = f" {normalize(text)} "
    return any(f" {word}" in padded for word in REVIEW)


def is_trade_idea(text: str) -> bool:
    """Une idée de trade chiffrée (sens + stop + prix) : pour la check-list, pas pour Claude.
    Constaté : « je vend l'or a 4108 stop a 4132 » partait à l'analyse."""
    padded = f" {normalize(text)} "
    words = set(padded.split())
    if any(f" {word}" in padded for word in ASK_ANALYSIS):
        return False
    return bool(words & set(DIRECTIONS)) and bool(words & set(STOPS)) and any(
        c.isdigit() for c in text)  # fmt: skip


class TradingMode:
    def __init__(self) -> None:
        self.enabled = False

    @staticmethod
    def command(text: str) -> str | None:
        """« on », « off », ou None si la phrase n'est pas une commande du mode."""
        words = _command_words(text)
        if any(words == p or words.startswith(p + " ") for p in OFF):
            return "off"
        if any(words == p or words.startswith(p + " ") for p in ON) and len(words.split()) <= 7:
            return "on"
        return None

    def route(self, text: str, choose: Callable[[str], set[str]] | None = None) -> str:
        """« local » (modèle local) ou « analysis » (paquet pour Claude, après aperçu)."""
        padded = f" {normalize(text)} "
        if is_review(text):
            return "analysis"
        if any(f" {key}" in padded for key in LOCAL) or is_trade_idea(text):
            return "local"
        if choose is not None and choose(text) & OTHER_SKILLS:
            return "local"
        return "analysis"
