"""Rapport COT de la CFTC (gratuit, chaque vendredi, données du mardi) : le positionnement net
des grands spéculateurs (« non-commerciaux ») sur les contrats à terme liés à l'instrument,
et sa variation sur la semaine. Calculé ici ; seul le résumé part."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import httpx

from friday.trading.cache import cached_text
from friday.trading.calendar import HEADERS, SourceUnavailable, short_error
from friday.trading.instruments import Instrument

URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
KEEP_SECONDS = 6 * 3600
# Marché COT de chaque devise ou actif (début du nom dans le rapport)
MARKETS = {
    "EUR": "EURO FX - ", "GBP": "BRITISH POUND - ", "JPY": "JAPANESE YEN - ",
    "CHF": "SWISS FRANC - ", "CAD": "CANADIAN DOLLAR - ", "AUD": "AUSTRALIAN DOLLAR - ",
    "NZD": "NZ DOLLAR - ", "USD": "USD INDEX - ", "XAUUSD": "GOLD - ", "XAGUSD": "SILVER - ",
    "USOIL": "WTI-PHYSICAL - ", "BTCUSD": "BITCOIN - CHICAGO", "ETHUSD": "ETHER CASH",
    "SPX": "E-MINI S&P 500 - ", "NDX": "NASDAQ MINI - ",
}  # fmt: skip
NAMES = {
    "EURO FX - ": "euro", "BRITISH POUND - ": "livre sterling", "JAPANESE YEN - ": "yen",
    "SWISS FRANC - ": "franc suisse", "CANADIAN DOLLAR - ": "dollar canadien",
    "AUSTRALIAN DOLLAR - ": "dollar australien", "NZ DOLLAR - ": "dollar néo-zélandais",
    "USD INDEX - ": "indice dollar (DXY)", "GOLD - ": "or", "SILVER - ": "argent",
    "WTI-PHYSICAL - ": "pétrole WTI", "BITCOIN - CHICAGO": "bitcoin", "ETHER CASH": "ether",
    "E-MINI S&P 500 - ": "S&P 500", "NASDAQ MINI - ": "Nasdaq 100",
}  # fmt: skip
# Colonnes du rapport « legacy », contrats à terme seuls
DATE, LONG, SHORT, CHANGE_LONG, CHANGE_SHORT = 2, 8, 9, 38, 39


@dataclass
class Positioning:
    market: str
    date: str
    longs: int
    shorts: int
    change_net: int

    @property
    def net(self) -> int:
        return self.longs - self.shorts


def load(cache_path: Path | None = None, get=httpx.get) -> tuple[list[list[str]], float | None]:
    """(lignes du rapport, âge si c'est une vieille copie faute de mieux)."""

    def download() -> str:
        response = get(URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.text

    try:
        text, age = cached_text(cache_path, KEEP_SECONDS, download)
        return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text))], age
    except (httpx.HTTPError, csv.Error) as error:
        raise SourceUnavailable(
            f"Rapport COT momentanément indisponible ({short_error(error)})."
        ) from error


def positioning(rows: list[list[str]], prefix: str) -> Positioning | None:
    for row in rows:
        if len(row) > CHANGE_SHORT and row[0].upper().startswith(prefix):
            try:
                change = int(row[CHANGE_LONG]) - int(row[CHANGE_SHORT])
                return Positioning(NAMES.get(prefix, row[0].split(" - ")[0]), row[DATE],
                                   int(row[LONG]), int(row[SHORT]), change)  # fmt: skip
            except ValueError:
                return None
    return None


def markets_for(instrument: Instrument) -> list[str]:
    keys = [instrument.symbol] if instrument.symbol in MARKETS else list(instrument.currencies)
    return [MARKETS[k] for k in keys if k in MARKETS]


def _n(value: int, sign: bool = False) -> str:
    return (f"{value:+,}" if sign else f"{value:,}").replace(",", " ")


def text(found: list[Positioning]) -> str:
    if not found:
        return "Pas de marché COT correspondant à cet instrument."
    lines = [f"Rapport COT de la CFTC (au {found[0].date}, grands spéculateurs, contrats) :"]
    for p in found:
        side = "acheteurs" if p.net >= 0 else "vendeurs"
        lines.append(f"- {p.market} : nets {side} {_n(abs(p.net))} (achats {_n(p.longs)}, "
                     f"ventes {_n(p.shorts)}), variation sur la semaine "
                     f"{_n(p.change_net, True)}.")  # fmt: skip
    return "\n".join(lines)
