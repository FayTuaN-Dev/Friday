"""Séances de marché (forex) : lesquelles sont ouvertes maintenant, et l'heure qu'il est.
Calculé sur le PC ; changements d'heure gérés par les fuseaux de chaque place."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def french(moment: datetime, with_day: bool = True) -> str:
    """« mercredi 07/10 00:09 » (heure de Paris), sans dépendre de la langue de Windows."""
    local = moment.astimezone(PARIS)
    return (f"{DAYS[local.weekday()]} " if with_day else "") + f"{local:%d/%m %H:%M}"


SESSIONS = (  # (nom, fuseau, ouverture, fermeture en heure locale)
    ("Sydney", "Australia/Sydney", 7, 16),
    ("Tokyo", "Asia/Tokyo", 9, 18),
    ("Londres", "Europe/London", 8, 17),
    ("New York", "America/New_York", 8, 17),
)
NEW_YORK = ZoneInfo("America/New_York")


def forex_closed(now: datetime) -> bool:
    """Le forex ferme le vendredi 17 h à New York et rouvre le dimanche 17 h."""
    ny = now.astimezone(NEW_YORK)
    return (ny.weekday() == 4 and ny.hour >= 17) or ny.weekday() == 5 or (
        ny.weekday() == 6 and ny.hour < 17)  # fmt: skip


def open_sessions(now: datetime) -> list[str]:
    if forex_closed(now):
        return []
    found = []
    for name, zone, start, end in SESSIONS:
        local = now.astimezone(ZoneInfo(zone))
        if local.weekday() < 5 and start <= local.hour < end:
            found.append(name)
    return found


def next_opening(now: datetime) -> tuple[str, datetime] | None:
    best = None
    for name, zone, start, _ in SESSIONS:
        local = now.astimezone(ZoneInfo(zone))
        for days in range(0, 4):
            day = (local + timedelta(days=days)).replace(hour=start, minute=0, second=0,
                                                          microsecond=0)  # fmt: skip
            if day > local and day.weekday() < 5:
                if best is None or day < best[1]:
                    best = (name, day)
                break
    return best


def trading_window(now: datetime, hours: tuple[int, int]) -> str:
    """Où en est la plage de trading de l'utilisateur (heure de Paris)."""
    from friday.trading.calendar import delay

    local = now.astimezone(PARIS)
    start = local.replace(hour=hours[0], minute=0, second=0, microsecond=0)
    end = local.replace(hour=hours[1], minute=0, second=0, microsecond=0)
    span = f"Plage de trading de l'utilisateur : {hours[0]} h – {hours[1]} h (Paris)"
    if local.weekday() >= 5:
        return f"{span} : week-end."
    if local < start:
        return f"{span} : commence dans {delay((start - local).total_seconds() / 60)}."
    if local < end:
        return f"{span} : en cours, encore {delay((end - local).total_seconds() / 60)}."
    return f"{span} : terminée pour aujourd'hui."


def text(now: datetime, hours: tuple[int, int] | None = None) -> str:
    paris = now.astimezone(PARIS)
    sessions = open_sessions(now)
    if forex_closed(now):
        state = "Marché des changes fermé (week-end)."
    elif sessions:
        overlap = " (chevauchement : volatilité souvent plus forte)" if len(sessions) > 1 else ""
        state = f"Séances ouvertes : {', '.join(sessions)}{overlap}."
    else:
        state = "Aucune grande séance ouverte (marché calme)."
    upcoming = next_opening(now)
    after = (f" Prochaine ouverture : {upcoming[0]} à {upcoming[1].astimezone(PARIS):%H:%M} "
             "(Paris).") if upcoming else ""  # fmt: skip
    window = f" {trading_window(now, hours)}" if hours else ""
    return f"Il est {french(paris)} à Paris ({now:%H:%M} UTC). {state}{after}{window}"
