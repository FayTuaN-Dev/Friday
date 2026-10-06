"""Calendrier économique (ForexFactory, flux public de la semaine, gratuit, sans clé) : les
annonces à fort et moyen impact des devises de l'instrument, de 12 h avant à 48 h après.

Source non officielle : en cas de panne, `SourceUnavailable` (l'analyse part sans).
Le flux est gardé une heure sur le disque (data/cache) : le site bloque si on l'interroge
sans cesse (« 429 », constaté) ; en cas de panne, la dernière version connue sert, avec son âge.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from friday.trading.cache import cached_text

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
KEEP_SECONDS = 3600
PARIS = ZoneInfo("Europe/Paris")
IMPACTS = {"High": "fort", "Medium": "moyen"}


class SourceUnavailable(Exception):
    """Message destiné à l'utilisateur."""


@dataclass
class Event:
    time: datetime  # avec fuseau
    currency: str
    title: str
    impact: str  # High, Medium, Low, Holiday
    forecast: str
    previous: str


def short_error(error: Exception) -> str:
    """« code 429 : trop de demandes » plutôt qu'une URL et un lien en anglais."""
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        return f"code {code}" + (" : trop de demandes, réessayez plus tard" if code == 429 else "")
    return type(error).__name__


def parse(text: str) -> list[Event]:
    return [
        Event(datetime.fromisoformat(e["date"]), e.get("country", ""), e.get("title", ""),
              e.get("impact", ""), e.get("forecast", ""), e.get("previous", ""))
        for e in json.loads(text)
    ]  # fmt: skip


def load(cache_path: Path | None = None, get=httpx.get) -> tuple[list[Event], float | None]:
    """(annonces de la semaine, âge si c'est une vieille copie faute de mieux)."""

    def download() -> str:
        response = get(URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text

    try:
        text, age = cached_text(cache_path, KEEP_SECONDS, download)
        return parse(text), age
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise SourceUnavailable(
            f"Calendrier économique momentanément indisponible ({short_error(error)})."
        ) from error


def relevant(events: list[Event], currencies: tuple[str, ...], now: datetime,
             before_h: int = 12, after_h: int = 48) -> list[Event]:  # fmt: skip
    """Annonces à fort / moyen impact des `currencies` (et celles qui touchent tout le monde)."""
    start, end = now - timedelta(hours=before_h), now + timedelta(hours=after_h)
    return sorted(
        (e for e in events
         if e.impact in IMPACTS and (e.currency in currencies or e.currency == "All")
         and start <= e.time <= end),
        key=lambda e: e.time,
    )  # fmt: skip


def _french(moment):
    from friday.trading.sessions import french

    return french(moment)


def text(events: list[Event], now: datetime) -> str:
    if not events:
        return "Aucune annonce à fort ou moyen impact de 12 h avant à 48 h après (ForexFactory)."
    lines = ["Annonces économiques (ForexFactory ; heure de Paris ; « passée » = déjà publiée) :"]
    for e in events:
        state = "passée" if e.time <= now else "à venir"
        figures = ", ".join(part for part in (
            f"prévision {e.forecast}" if e.forecast else "",
            f"précédent {e.previous}" if e.previous else "") if part)  # fmt: skip
        lines.append(f"- {_french(e.time)} · {e.currency} · impact {IMPACTS[e.impact]} · "
                     f"{e.title}{f' ({figures})' if figures else ''} · {state}")  # fmt: skip
    return "\n".join(lines)
