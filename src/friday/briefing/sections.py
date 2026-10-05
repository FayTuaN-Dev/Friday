"""Contenu de chaque rubrique du briefing. Une rubrique sans rien à dire renvoie None :
elle est alors passée sous silence (pas de « vous n'avez aucun rappel »)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from friday.briefing.config import Section

log = logging.getLogger(__name__)


@dataclass
class Sources:
    """Où chercher les informations ; une source absente rend sa rubrique muette."""

    weather: Callable[[str], str | None] | None = None  # ville (vide = par défaut) → texte
    agenda: object | None = None  # AgendaStore
    news: Callable[[str], list[str]] | None = None  # sujet → titres
    calendar: Callable[[date], list[str]] | None = None  # jour → événements (Google)
    mail: Callable[[], list[str]] | None = None  # mails non lus (Google)


def gather(section: Section, sources: Sources, now: datetime) -> str | None:
    try:
        return _GATHERERS[section.kind](section, sources, now)
    except Exception as error:  # une rubrique en panne (réseau…) ne gâche pas le briefing
        log.warning("Rubrique « %s » indisponible : %s", section.label(), error)
        return None


def _weather(section, sources, now):
    text = sources.weather(section.value) if sources.weather else None
    if not text:  # aucune ville connue : on se tait plutôt que d'inventer
        return None
    return f"{text}\n(Ne garde que la journée d'aujourd'hui.)"


def _reminders(section, sources, now):
    if sources.agenda is None:
        return None
    today = [r for r in sources.agenda.pending() if r.due_at.date() == now.date()]
    if not today:
        return None
    return "\n".join(f"- à {r.due_at:%H:%M} : {r.text}" for r in today)


def _calendar(section, sources, now):
    if sources.calendar is None:
        return None
    return "\n".join(f"- {line}" for line in sources.calendar(now.date())) or None


def _mail(section, sources, now):
    if sources.mail is None:
        return None
    lines = sources.mail()
    return "\n".join(f"- {line}" for line in lines) or None


def _list(section, sources, now):
    if sources.agenda is None:
        return None
    from friday.tools.notes import list_key

    notes = sources.agenda.notes(list_key(section.value))
    return "\n".join(f"- {n.text}" for n in notes) or None


def _news(section, sources, now):
    if sources.news is None:
        return None
    titles = sources.news(section.value)
    return "\n".join(f"- {t}" for t in titles[:3]) or None


def _free(section, sources, now):
    return (
        f"Consigne : {section.value} (une ou deux phrases, de ton cru)." if section.value else None
    )


_GATHERERS = {
    "meteo": _weather,
    "agenda": _calendar,
    "rappels": _reminders,
    "mails": _mail,
    "liste": _list,
    "actualites": _news,
    "libre": _free,
}
