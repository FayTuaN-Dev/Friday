"""La météo du trajet (I3) : pluie, rafales ou verglas à l'aller ou au retour d'un rendez-vous
→ « la voiture plutôt que la moto ». Prévisions heure par heure d'Open-Meteo (gratuit, sans
clé) au lieu du rendez-vous, gardées 30 min."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from friday.initiative.departure import spoken_time
from friday.tools.weather import FORECAST_URL

log = logging.getLogger(__name__)

HOURLY = "precipitation,precipitation_probability,wind_gusts_10m,temperature_2m"
KEEP = 1800  # secondes
RAIN_MM = 0.3  # par heure : en dessous, quelques gouttes
RAIN_CHANCE = 60  # %
GUSTS = 60  # km/h : désagréable, voire dangereux à moto
FROST = 1  # °C : risque de verglas


@dataclass(frozen=True)
class Hour:
    at: datetime
    rain_mm: float
    rain_chance: float
    gusts: float
    temperature: float


def risks(hour: Hour) -> list[str]:
    found = []
    if hour.rain_mm >= RAIN_MM or hour.rain_chance >= RAIN_CHANCE:
        found.append("pluie")
    if hour.gusts >= GUSTS:
        found.append(f"rafales à {round(hour.gusts)} km/h")
    if hour.temperature <= FROST:
        found.append("risque de verglas")
    return found


def advice(hours: list[Hour], way_out: tuple[datetime, datetime],
           way_back: tuple[datetime, datetime]) -> str:  # fmt: skip
    """La phrase météo à ajouter à l'annonce de départ ("" : prévisions inconnues)."""

    def first_bad(start: datetime, end: datetime) -> tuple[Hour, list[str]] | None:
        for hour in hours:
            # l'heure de prévision couvre [at, at + 1 h[ : celle qui touche le trajet compte
            if start.replace(minute=0, second=0, microsecond=0) <= hour.at <= end:
                if found := risks(hour):
                    return hour, found
        return None

    def covered(start: datetime, end: datetime) -> bool:
        return any(start.replace(minute=0, second=0, microsecond=0) <= h.at <= end for h in hours)

    if not covered(*way_out):
        return ""
    out, back = first_bad(*way_out), first_bad(*way_back)
    if out is None and back is None:
        return " Temps sec sur le trajet : la moto passe."
    hour, found = out or back
    when = "à l'aller" if out else f"au retour, vers {spoken_time(hour.at)}"
    what = " et ".join(dict.fromkeys(found))
    return f" Attention, {what} {when} : la voiture plutôt que la moto."


class TripWeather:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=8)
        self._kept: dict[tuple[float, float], tuple[float, list[Hour]]] = {}

    def hours(self, lat: float, lon: float) -> list[Hour]:
        """Prévisions heure par heure (aujourd'hui et demain) ; [] si injoignable."""
        key = (round(lat, 2), round(lon, 2))
        kept = self._kept.get(key)
        if kept and time.monotonic() - kept[0] < KEEP:
            return kept[1]
        try:
            response = self.client.get(FORECAST_URL, params={
                "latitude": lat, "longitude": lon, "hourly": HOURLY,
                "timezone": "auto", "forecast_days": 2,
            })  # fmt: skip
            response.raise_for_status()
            data = response.json()["hourly"]
        except (httpx.HTTPError, KeyError, ValueError) as error:
            log.info("Météo du trajet impossible : %s", error)
            return []
        hours = [
            Hour(
                datetime.fromisoformat(at),
                mm or 0,
                chance or 0,
                gusts or 0,
                temp if temp is not None else 10,
            )  # fmt: skip
            for at, mm, chance, gusts, temp in zip(
                data["time"],
                data["precipitation"],
                data["precipitation_probability"],
                data["wind_gusts_10m"],
                data["temperature_2m"],
                strict=False,
            )  # fmt: skip
        ]
        self._kept[key] = (time.monotonic(), hours)
        return hours
