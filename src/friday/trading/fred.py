"""Résultats officiels des grandes annonces américaines (FRED, Fed de Saint-Louis : gratuit,
clé gratuite à créer sur fredaccount.stlouisfed.org). ForexFactory ne donne que la prévision
et le précédent ; FRED donne la dernière valeur publiée, avec sa période.

Calcul sur le PC selon la nature de l'indicateur : niveau, variation (créations d'emplois),
variation sur un mois ou sur un an (inflation, ventes).
"""

from dataclasses import dataclass
from pathlib import Path

import httpx

from friday.trading.cache import cached_text
from friday.trading.calendar import SourceUnavailable, short_error

URL = "https://api.stlouisfed.org/fred/series/observations"
KEEP_SECONDS = 3600


@dataclass(frozen=True)
class Series:
    words: tuple[str, ...]  # mots du titre ForexFactory (minuscules)
    series: str  # identifiant FRED
    how: str  # « niveau », « variation », « mensuel % », « annuel % »
    unit: str = ""


# Du plus précis au plus général : « Core CPI m/m » avant « CPI m/m »
SERIES = (
    Series(("non-farm employment change",), "PAYEMS", "variation", "k emplois"),
    Series(("unemployment rate",), "UNRATE", "niveau", "%"),
    Series(("unemployment claims",), "ICSA", "niveau", " inscriptions"),
    Series(("core cpi m/m",), "CPILFESL", "mensuel %"),
    Series(("core cpi y/y",), "CPILFESL", "annuel %"),
    Series(("cpi m/m",), "CPIAUCSL", "mensuel %"),
    Series(("cpi y/y",), "CPIAUCSL", "annuel %"),
    Series(("core pce price index m/m",), "PCEPILFE", "mensuel %"),
    Series(("core retail sales m/m",), "RSFSXMV", "mensuel %"),
    Series(("retail sales m/m",), "RSAFS", "mensuel %"),
    Series(("federal funds rate",), "DFEDTARU", "niveau", "% (borne haute)"),
    Series(("gdp q/q",), "A191RL1Q225SBEA", "niveau", "% (rythme annualisé)"),
)  # fmt: skip


def series_for(title: str, currency: str) -> Series | None:
    if currency != "USD":
        return None
    lowered = title.lower()
    return next((s for s in SERIES if any(w in lowered for w in s.words)), None)


def observations(series: str, key: str, cache_dir: Path | None = None,
                 get=httpx.get) -> list[tuple[str, float]]:  # fmt: skip
    """[(date, valeur)], de la plus récente à la plus ancienne (14 dernières)."""

    def download() -> str:
        response = get(URL, params={"series_id": series, "api_key": key, "file_type": "json",
                                    "sort_order": "desc", "limit": 14}, timeout=10)  # fmt: skip
        response.raise_for_status()
        return response.text

    import json

    path = cache_dir / f"fred_{series}.json" if cache_dir else None
    try:
        text, _ = cached_text(path, KEEP_SECONDS, download)
        rows = json.loads(text)["observations"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise SourceUnavailable(f"FRED indisponible ({short_error(error)}).") from error
    return [(r["date"], float(r["value"])) for r in rows if r.get("value") not in (".", None)]


def latest(spec: Series, rows: list[tuple[str, float]]) -> str | None:
    """« 3.8 % (période 2026-09-01) » selon la nature de l'indicateur."""
    if not rows:
        return None
    date, value = rows[0]
    if spec.how == "niveau":
        shown = f"{value:,.0f}".replace(",", " ") if value >= 1000 else f"{value:g}"
        return f"{shown}{spec.unit} (période {date})"
    if spec.how == "variation" and len(rows) >= 2:
        return (
            f"{value - rows[1][1]:+,.0f}{' ' + spec.unit}".replace(",", " ") + f" (période {date})"
        )
    if spec.how == "mensuel %" and len(rows) >= 2:
        return f"{(value / rows[1][1] - 1) * 100:+.1f} % sur un mois (période {date})"
    if spec.how == "annuel %" and len(rows) >= 13:
        return f"{(value / rows[12][1] - 1) * 100:+.1f} % sur un an (période {date})"
    return None


class FredResults:
    """Pour une annonce passée : sa dernière valeur publiée chez FRED (ou None)."""

    def __init__(self, key: str, cache_dir: Path | None = None, fetch=observations) -> None:
        self.key, self.cache_dir, self.fetch = key, cache_dir, fetch

    def __call__(self, title: str, currency: str) -> str | None:
        spec = series_for(title, currency)
        if spec is None or not self.key:
            return None
        return latest(spec, self.fetch(spec.series, self.key, self.cache_dir))
