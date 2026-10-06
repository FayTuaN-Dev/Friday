"""Mode trading : activé / désactivé à la voix ou au clavier (« mode trading », « fin du mode
trading »), reconnu par du code avant le modèle. Hors de ce mode, rien ne change.

En mode trading, l'aiguillage est déterministe :
- calculs de risque, journal, et tout ce qui relève d'une autre compétence (mails, PC…)
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
LOCAL = (
    # calculs de risque (déterministes, sur ce PC)
    "taille de position", "combien de lots", "nombre de lots", "combien de lot", "valeur du pip",
    "valeur d un pip", "ratio", "risque rendement", "risk reward", "perte max", "calcule",
    "combien je risque", "combien je perds",
    # journal (local)
    "journal", "mes trades", "note le trade", "enregistre le trade", "ajoute un trade",
    "nouveau trade", "cloture le trade", "ferme le trade", "mon bilan", "mes statistiques",
    "mes performances",
)  # fmt: skip
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
        if any(f" {key}" in padded for key in LOCAL):
            return "local"
        if choose is not None and choose(text) & OTHER_SKILLS:
            return "local"
        return "analysis"
