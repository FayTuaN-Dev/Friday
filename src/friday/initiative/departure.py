"""« Il faut partir dans 15 minutes » (I1) : pour un événement de l'agenda qui a une adresse,
Friday calcule l'heure de départ depuis la maison et prévient un quart d'heure avant."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from friday.google.calendar import Event
from friday.tools.route import duration_text

MARGIN = 1.15  # OpenStreetMap ne voit pas les bouchons : 15 % de route en plus
SPARE = timedelta(minutes=5)  # se garer, marcher jusqu'à la porte
LEAD = timedelta(minutes=15)  # prévenir un quart d'heure avant l'heure de départ
SHORT = 180  # moins de 3 min de route : c'est à côté, rien à dire
_POSTCODE = re.compile(r"^\d{5}\s+(.+)$")


@dataclass(frozen=True)
class Trip:
    event: Event
    seconds: float  # de route, sans les bouchons

    @property
    def leave_at(self) -> datetime:
        return self.event.start - timedelta(seconds=self.seconds * MARGIN) - SPARE

    def due(self, now: datetime) -> bool:
        """Le moment de prévenir : moins d'un quart d'heure avant le départ, avant le début."""
        return (not self.event.all_day and self.seconds >= SHORT
                and self.leave_at - LEAD <= now < self.event.start)  # fmt: skip


def key(event: Event) -> str:
    return f"depart:{event.id}:{event.start:%Y-%m-%d %H:%M}"  # déplacé = nouveau sujet


def spoken_time(moment: datetime) -> str:
    """« 16 h », « 16 h 05 » : lu correctement par la voix (« 16:05 » ne l'est pas toujours)."""
    return f"{moment.hour} h" if moment.minute == 0 else f"{moment.hour} h {moment.minute:02d}"


def place_name(location: str) -> str:
    """« 12 rue des Lilas, 85500 Les Herbiers, France » → « Les Herbiers »."""
    parts = [p.strip() for p in location.split(",") if p.strip()]
    for part in parts:
        if found := _POSTCODE.match(part):
            return found.group(1)
    return parts[0] if parts else location


def departure_text(trip: Trip, now: datetime) -> str:
    event, leave = trip.event, trip.leave_at
    minutes = round((leave - now).total_seconds() / 60)
    if minutes <= 0:
        when = "il faudrait déjà être parti"
    else:
        when = f"il faudrait partir vers {spoken_time(leave)}, dans {minutes} minute" + (
            "s" if minutes > 1 else ""
        )
    road = duration_text(trip.seconds * MARGIN)
    return (
        f"Dis EXACTEMENT : « {event.title} à {spoken_time(event.start)}, à "
        f"{place_name(event.location)} : environ {road} de route, {when}. »"
    )
