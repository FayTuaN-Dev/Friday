"""Retrouver l'événement dont parle l'utilisateur. Le LLM donne ce qu'il a compris (« 1 »,
« le rendez-vous à la banque », rien du tout pour « supprime-le ») et Friday cherche :
le modèle local invente souvent un identifiant au lieu de recopier le vrai."""

from datetime import date, timedelta

from friday.google.calendar import Event, GoogleCalendar
from friday.voice.wake import normalize

PRONOUNS = {"", "le", "la", "l", "celui ci", "celle ci", "ce rendez vous", "cet evenement", "it"}
FILLERS = {"le", "la", "les", "l", "de", "du", "des", "a", "au", "mon", "ma", "rendez", "vous",
           "rdv", "evenement", "chez", "un", "une"}  # fmt: skip
LOOK_AHEAD_DAYS = 60


class EventNotFound(ValueError):
    pass


class RecentEvents:
    """Les événements dont on vient de parler (dernière liste, ou dernier ajout)."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def remember(self, events: list[Event]) -> None:
        self.events = list(events)


def find_event(ref: str, recent: RecentEvents, calendar: GoogleCalendar, today: date) -> Event:
    said = normalize(ref or "")
    by_id = {e.id: e for e in recent.events}
    if ref in by_id:
        return by_id[ref]
    if said.isdigit() and 1 <= int(said) <= len(recent.events):  # « le numéro 2 »
        return recent.events[int(said) - 1]
    if said in PRONOUNS:
        if len(recent.events) == 1:  # « supprime-le » juste après l'avoir ajouté ou listé
            return recent.events[0]
        raise EventNotFound("précise de quel événement il s'agit (son titre ou son jour)")
    words = [w for w in said.split() if w not in FILLERS] or said.split()
    upcoming = calendar.between(today, today + timedelta(days=LOOK_AHEAD_DAYS))
    for pool in (recent.events, upcoming):
        matches = [e for e in pool if all(w in normalize(e.title) for w in words)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(f"« {e.title} » ({e.start:%d/%m %H:%M})" for e in matches[:4])
            raise EventNotFound(f"plusieurs événements correspondent : {names}")
    if len(ref) > 15 and " " not in ref:  # un vrai identifiant Google
        return calendar.get(ref)
    raise EventNotFound(f"aucun événement « {ref} » dans les {LOOK_AHEAD_DAYS} prochains jours")
