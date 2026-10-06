"""Cours de référence officiels de la BCE (via Frankfurter, gratuit, sans clé) : publiés une
fois par jour ouvré vers 16 h, ce sont des cours de référence, pas des cours en temps réel."""

import httpx

URL = "https://api.frankfurter.dev/v1/latest"
TIMEOUT = 10


class RatesUnavailable(Exception):
    """Message destiné à l'utilisateur."""


def reference_rate(base: str, quote: str, get=httpx.get) -> tuple[float, str]:
    """(cours, date de publication) : 1 `base` = cours `quote`."""
    try:
        response = get(URL, params={"base": base, "symbols": quote}, timeout=TIMEOUT,
                       follow_redirects=True)  # fmt: skip
        response.raise_for_status()
        data = response.json()
        return float(data["rates"][quote]), str(data["date"])
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise RatesUnavailable(f"Cours BCE {base}/{quote} indisponible ({error}).") from error
