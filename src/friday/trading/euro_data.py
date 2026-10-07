"""Données officielles de la zone euro, gratuites et sans clé, pour les instruments en euro :
inflation (Eurostat : la BCE ne publie plus la série depuis le changement de nomenclature de
2026, constaté), chômage et taux de dépôt de la BCE (portail de données de la BCE).

Gardées 12 h sur le disque (data/cache) : elles changent une fois par mois au plus.
"""

import csv
import io
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx

from friday.trading.cache import cached_text
from friday.trading.calendar import SourceUnavailable, short_error

EUROSTAT = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr"
            "?geo=EA&coicop18=TOTAL&unit=RCH_A&lastTimePeriod=3&format=JSON")  # fmt: skip
ECB = "https://data-api.ecb.europa.eu/service/data/{key}?format=csvdata&lastNObservations={n}"
UNEMPLOYMENT = "LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T"
DEPOSIT_RATE = "FM/B.U2.EUR.4F.KR.DFR.LEV"
KEEP_SECONDS = 12 * 3600
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
          "octobre", "novembre", "décembre")  # fmt: skip

Get = Callable[..., httpx.Response]


def _download(url: str, get: Get) -> str:
    response = get(url, timeout=20)
    response.raise_for_status()
    return response.text


def inflation(text: str) -> list[tuple[str, float]]:
    """JSON Eurostat → [(« 2026-09 », 3.8), …], du plus ancien au plus récent."""
    data = json.loads(text)
    times = data["dimension"]["time"]["category"]["index"]
    found = [(period, data["value"].get(str(i))) for period, i in times.items()]
    return sorted((p, float(v)) for p, v in found if v is not None)


def ecb_series(text: str) -> list[tuple[str, float]]:
    """CSV de la BCE → [(période, valeur)], du plus ancien au plus récent."""
    rows = csv.DictReader(io.StringIO(text))
    return sorted((r["TIME_PERIOD"], float(r["OBS_VALUE"])) for r in rows if r.get("OBS_VALUE"))


def month(period: str) -> str:
    year, number = period.split("-")[:2]
    return f"{MONTHS[int(number) - 1]} {year}"


def pct(value: float) -> str:
    return f"{value:g} %".replace(".", ",")


def text(cache_dir: Path | None = None, get: Get = httpx.get) -> str:
    """Le bloc « zone euro » ; SourceUnavailable si aucune des trois séries ne répond."""
    cache = (lambda name: cache_dir / name) if cache_dir else (lambda name: None)
    parts = []
    for name, url, parse, say in (
        ("eurostat_hicp.json", EUROSTAT, inflation, _say_inflation),
        ("ecb_unemployment.csv", ECB.format(key=UNEMPLOYMENT, n=2), ecb_series, _say_unemployment),
        ("ecb_deposit_rate.csv", ECB.format(key=DEPOSIT_RATE, n=2), ecb_series, _say_rate),
    ):  # fmt: skip
        try:
            raw, _ = cached_text(cache(name), KEEP_SECONDS, lambda u=url: _download(u, get))
            series = parse(raw)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            parts.append(f"({name.split('.')[0]} indisponible : {short_error(error)})")
            continue
        if series:
            parts.append(say(series))
    if all(p.startswith("(") for p in parts):
        raise SourceUnavailable("Données de la zone euro momentanément indisponibles.")
    return "Zone euro (sources officielles) : " + " ; ".join(parts) + "."


def _say_inflation(series: list[tuple[str, float]]) -> str:
    (last, value), before = series[-1], series[:-1]
    earlier = ", ".join(f"{pct(v)} en {month(p).split()[0]}" for p, v in reversed(before))
    return (f"inflation {pct(value)} sur un an en {month(last)} (Eurostat)"
            + (f", après {earlier}" if earlier else ""))  # fmt: skip


def _say_unemployment(series: list[tuple[str, float]]) -> str:
    last, value = series[-1]
    return f"chômage {pct(value)} en {month(last)} (BCE)"


def _say_rate(series: list[tuple[str, float]]) -> str:
    (day, value), before = series[-1], series[:-1]
    since = date.fromisoformat(day).strftime("%d/%m/%Y")
    return (f"taux de dépôt de la BCE {pct(value)} depuis le {since}"
            + (f" (avant : {pct(before[-1][1])})" if before else ""))  # fmt: skip
