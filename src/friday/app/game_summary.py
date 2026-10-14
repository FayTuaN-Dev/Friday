"""Le résumé du retour de mode jeu (G3) : « Me revoilà. Pendant votre partie (1 h 25) :
2 rappels et 3 nouveaux mails. » Les annonces gardées de côté suivent juste après."""

import logging
from collections.abc import Callable
from datetime import datetime

log = logging.getLogger(__name__)

NAMES = {"rappel": ("rappel", "rappels")}
OTHER = ("tâche terminée", "tâches terminées")


def length(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest:02d}" if rest else f"{hours} h"


def unread_mails(google) -> int | None:
    """Mails non lus (None : pas de compte, déconnecté ou réseau en panne)."""
    try:
        if google is None or not google.connected:
            return None
        from friday.google.gmail import Gmail

        return Gmail(lambda: google.service("gmail", "v1")).unread_total()
    except Exception as error:
        log.info("Mode jeu : mails non comptés (%s)", error)
        return None


class GameSummary:
    def __init__(self, google=None, clock: Callable[[], datetime] = datetime.now) -> None:
        self.google = google
        self.clock = clock
        self.since = clock()
        self.unread = unread_mails(google)  # au début de la partie

    def text(self, missed: list[str]) -> str:
        """`missed` : les tâches gardées de côté pendant la partie (« rappel »…)."""
        parts = []
        counts: dict[tuple[str, str], int] = {}
        for task in missed:
            words = NAMES.get(task, OTHER)
            counts[words] = counts.get(words, 0) + 1
        parts += [f"{n} {words[n > 1]}" for words, n in counts.items()]
        now_unread = unread_mails(self.google)
        if self.unread is not None and now_unread is not None and now_unread > self.unread:
            new = now_unread - self.unread
            parts.append(f"{new} nouveau{'x' if new > 1 else ''} mail{'s' if new > 1 else ''}")
        minutes = int((self.clock() - self.since).total_seconds() // 60)
        if not parts:
            return "Me revoilà."
        listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " et " + parts[-1]
        return f"Me revoilà. Pendant votre partie ({length(max(1, minutes))}) : {listed}."
