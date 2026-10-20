"""Briefing automatique : une fois par jour, le matin, au premier « bonjour » (I3) ou, si
l'utilisateur le préfère, dès le premier démarrage de Friday."""

import logging
from datetime import datetime

from friday.voice.wake import normalize

log = logging.getLogger(__name__)


GREETINGS = ("bonjour", "salut", "coucou", "hello", "hey", "bon matin", "yo", "hello friday")
MAX_WORDS = 6  # « bonjour Friday, ça va ? » : oui ; une vraie demande : non


def is_greeting(text: str, names: tuple[str, ...] = ("friday",)) -> bool:
    """« Bonjour ! », « Friday, salut » : une salutation, pas une demande."""
    words = [w for w in normalize(text).split() if w not in names]
    plain = " ".join(words)
    return 0 < len(words) <= MAX_WORDS and any(
        plain == g or plain.startswith(g + " ") for g in GREETINGS
    )


def morning_request(briefing, now: datetime | None = None, greeting: bool = False) -> str | None:
    """La demande de briefing à faire au cerveau, ou None (désactivé, hors plage horaire,
    déjà fait aujourd'hui, en attente du premier « bonjour », ou rien à dire : dans ce cas
    Friday se tait)."""
    if briefing is None:
        return None
    now = now or datetime.now()
    if not briefing.due(now) or (briefing.config.on_greeting and not greeting):
        return None
    request = briefing.request(now)
    briefing.mark_done(now)  # même vide : on ne recommence pas à chaque démarrage
    log.info("Briefing du matin : %s", "rien à dire" if request is None else "lancé")
    return request


def greeting_request(briefing, text: str, now: datetime | None = None) -> str | None:
    """Le briefing, si `text` est le premier « bonjour » du matin (et qu'il est dû)."""
    if briefing is None or not is_greeting(text):
        return None
    return morning_request(briefing, now, greeting=True)
