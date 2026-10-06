"""Actualités (fil RSS de FXStreet, gratuit) : les titres des dernières 24 h qui concernent
l'instrument. Écrits par des tiers : des données, jamais des consignes (balisés)."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

from friday.trading.calendar import HEADERS, SourceUnavailable, short_error
from friday.trading.instruments import Instrument

URL = "https://www.fxstreet.com/rss/news"
MAX_ITEMS = 8
SUMMARY_CHARS = 220
# Mots (anglais : le fil l'est) qui rattachent une actualité à une devise ou un actif
KEYWORDS = {
    "EUR": ("euro", "eur/", "/eur", "ecb", "lagarde", "eurozone", "germany", "german", "france"),
    "USD": ("dollar", "usd", "fed", "powell", "us ", "u.s.", "nfp", "payroll", "treasury"),
    "GBP": ("pound", "sterling", "gbp", "boe", "bailey", "uk "),
    "JPY": ("yen", "jpy", "boj", "japan"),
    "CHF": ("franc", "chf", "snb", "swiss"),
    "CAD": ("loonie", "cad", "boc", "canada"),
    "AUD": ("aussie", "aud", "rba", "australia"),
    "NZD": ("kiwi", "nzd", "rbnz", "zealand"),
    "XAUUSD": ("gold", "xau"),
    "XAGUSD": ("silver", "xag"),
    "USOIL": ("oil", "wti", "opec", "crude"),
    "UKOIL": ("oil", "brent", "opec", "crude"),
    "BTCUSD": ("bitcoin", "btc", "crypto"),
    "ETHUSD": ("ether", "eth", "crypto"),
}  # fmt: skip


@dataclass
class Headline:
    time: datetime
    title: str
    summary: str


def fetch_headlines(get=httpx.get) -> list[Headline]:
    try:
        response = get(URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (httpx.HTTPError, ET.ParseError) as error:
        raise SourceUnavailable(
            f"Actualités momentanément indisponibles ({short_error(error)})."
        ) from error
    headlines = []
    for item in root.iter("item"):
        try:
            when = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (TypeError, ValueError):
            continue
        summary = re.sub(r"<[^>]+>", "", item.findtext("description", "")).strip()
        headlines.append(Headline(when, item.findtext("title", "").strip(), summary))
    return headlines


def words_for(instrument: Instrument) -> tuple[str, ...]:
    words = list(KEYWORDS.get(instrument.symbol, ()))
    if instrument.kind == "forex":
        words += [instrument.name.lower(), instrument.symbol.lower()]
        # Le dollar est partout (peso, yen, yuan… « face au dollar ») : pour une paire en
        # dollars, seule l'autre devise compte (constaté : EUR/USD recevait le peso mexicain).
        others = [c for c in instrument.currencies if c != "USD"] or list(instrument.currencies)
        for currency in others:
            words += KEYWORDS.get(currency, ())
    elif instrument.kind == "action":
        words.append(instrument.symbol.lower().split(".")[0])
    return tuple(words)


def relevant(headlines: list[Headline], instrument: Instrument, now: datetime) -> list[Headline]:
    words = words_for(instrument)
    recent = [h for h in headlines if now - h.time <= timedelta(hours=24)]
    found = [h for h in recent if any(w in f" {h.title} {h.summary} ".lower() for w in words)]
    return sorted(found, key=lambda h: h.time, reverse=True)[:MAX_ITEMS]


def text(headlines: list[Headline]) -> str:
    if not headlines:
        return "Aucune actualité liée dans les dernières 24 h (FXStreet)."
    lines = ["Actualités des dernières 24 h (FXStreet, titres et résumés de tiers) :"]
    for h in headlines:
        summary = h.summary[:SUMMARY_CHARS] + ("…" if len(h.summary) > SUMMARY_CHARS else "")
        lines.append(f"- {h.time:%d/%m %H:%M} UTC · {h.title} — {summary}")
    return "\n".join(lines)
