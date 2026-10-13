"""Les sources de la veille monde (J9), gratuites et sans clé : les titres internationaux en
français (Le Monde, France 24) et les catastrophes en cours (GDACS, le système d'alerte de
l'ONU et de la Commission européenne : séismes, cyclones, inondations, volcans, incendies,
sécheresses). Écrits par des tiers : des données, jamais des consignes."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from friday.trading.calendar import SourceUnavailable

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
FEEDS = (
    ("Le Monde", "https://www.lemonde.fr/international/rss_full.xml"),
    ("France 24", "https://www.france24.com/fr/rss"),
)
GDACS = "https://www.gdacs.org/xml/rss.xml"
NS = {"gdacs": "http://www.gdacs.org", "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#"}
KINDS = {"EQ": "séisme", "TC": "cyclone", "FL": "inondations", "VO": "éruption volcanique",
         "WF": "grand incendie", "DR": "sécheresse"}  # fmt: skip
LEVELS = {"Red": "rouge", "Orange": "orange", "Green": "verte"}


class WorldUnavailable(SourceUnavailable):  # une source en panne : l'analyse continue sans
    pass


@dataclass(frozen=True)
class Headline:
    time: datetime
    title: str
    summary: str
    source: str
    link: str = ""  # l'article (clic dans la pop-up, U5)


@dataclass(frozen=True)
class Disaster:
    id: str
    kind: str  # EQ, TC, FL, VO, WF, DR
    level: str  # Red, Orange, Green
    country: str  # en anglais (GDACS)
    magnitude: float | None  # séismes seulement
    time: datetime  # ajout de l'alerte
    lat: float
    lon: float

    @property
    def major(self) -> bool:
        """À annoncer de soi-même : alerte rouge, ou séisme de magnitude 7 ou plus."""
        return self.level == "Red" or (self.kind == "EQ" and (self.magnitude or 0) >= 7)


def _get(url: str, get) -> bytes:
    try:
        response = get(url, headers=HEADERS, timeout=12, follow_redirects=True)
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as error:
        site = url.split("/")[2]
        raise WorldUnavailable(f"{site} indisponible ({type(error).__name__})") from error


def _date(text: str | None) -> datetime | None:
    try:
        when = parsedate_to_datetime(text or "")
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _clean(text: str | None) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return " ".join(text.replace("⁠", "").split())


def fetch_headlines(get=httpx.get) -> list[Headline]:
    """Les titres de tous les fils qui répondent ; WorldUnavailable si aucun ne répond."""
    found, errors = [], []
    for source, url in FEEDS:
        try:
            root = ET.fromstring(_get(url, get))
        except (WorldUnavailable, ET.ParseError) as error:
            errors.append(str(error))
            continue
        for item in root.iter("item"):
            when = _date(item.findtext("pubDate"))
            title = _clean(item.findtext("title"))
            if when is not None and title:
                summary = _clean(item.findtext("description"))
                link = (item.findtext("link") or "").strip()
                found.append(Headline(when, title, summary, source, link))
    if len(errors) == len(FEEDS):  # toutes en panne (une source vide, elle, a répondu)
        raise WorldUnavailable("Actualité internationale indisponible : " + " ; ".join(errors))
    return found


def fetch_disasters(get=httpx.get) -> list[Disaster]:
    try:
        root = ET.fromstring(_get(GDACS, get))
    except ET.ParseError as error:
        raise WorldUnavailable("GDACS illisible") from error
    found = []
    for item in root.iter("item"):
        if item.findtext("gdacs:iscurrent", "", NS) != "true":
            continue
        kind = item.findtext("gdacs:eventtype", "", NS)
        when = _date(item.findtext("gdacs:dateadded", None, NS) or item.findtext("pubDate"))
        if kind not in KINDS or when is None:
            continue
        severity = item.find("gdacs:severity", NS)
        try:
            quake = kind == "EQ" and severity is not None
            magnitude = float(severity.get("value")) if quake else None
            lat = float(item.findtext("geo:Point/geo:lat", "0", NS))
            lon = float(item.findtext("geo:Point/geo:long", "0", NS))
        except ValueError:
            continue
        found.append(Disaster(
            item.findtext("guid", "") or f"{kind}{when:%Y%m%d%H%M}", kind,
            item.findtext("gdacs:alertlevel", "Green", NS),
            item.findtext("gdacs:country", "", NS).split(",")[0].strip(), magnitude, when, lat, lon,
        ))  # fmt: skip
    return found
