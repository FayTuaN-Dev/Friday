"""Briefing automatique : une fois par jour, au premier démarrage de Friday le matin."""

import logging
from datetime import datetime

log = logging.getLogger(__name__)


def morning_request(briefing, now: datetime | None = None) -> str | None:
    """La demande de briefing à faire au cerveau, ou None (désactivé, hors plage horaire,
    déjà fait aujourd'hui, ou rien à dire : dans ce cas Friday se tait)."""
    if briefing is None:
        return None
    now = now or datetime.now()
    if not briefing.due(now):
        return None
    request = briefing.request(now)
    briefing.mark_done(now)  # même vide : on ne recommence pas à chaque démarrage
    log.info("Briefing du matin : %s", "rien à dire" if request is None else "lancé")
    return request
