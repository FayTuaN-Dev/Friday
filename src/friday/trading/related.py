"""Marchés liés à l'instrument : ce qui le fait bouger (dollar, taux américains, volatilité…),
lu chez Yahoo Finance avec sa variation depuis la veille. Constaté : sans eux, l'analyste
parlait « des rendements et du dollar » sans en avoir les chiffres."""

from collections.abc import Callable
from dataclasses import dataclass

from friday.trading.instruments import Instrument
from friday.trading.market import MarketUnavailable, fetch


@dataclass(frozen=True)
class Related:
    key: str
    ticker: str
    name: str
    is_rate: bool = False  # un taux (en %) : variation en points, pas en %


DXY = Related("DXY", "DX-Y.NYB", "indice dollar (DXY)")
US10Y = Related("US10Y", "^TNX", "taux américain à 10 ans (%)", is_rate=True)
VIX = Related("VIX", "^VIX", "VIX (peur des marchés actions)")
GOLD = Related("GOLD", "GC=F", "or (contrat à terme)")
SILVER = Related("SILVER", "SI=F", "argent (contrat à terme)")
SPX = Related("SPX", "^GSPC", "S&P 500")
OIL = Related("OIL", "CL=F", "pétrole WTI")
BY_KIND = {
    "forex": (DXY, US10Y, VIX),
    "metal": (DXY, US10Y, VIX, GOLD, SILVER),  # or et argent : pour leur rapport
    "energie": (DXY, VIX, SPX),
    "indice": (VIX, US10Y, DXY),
    "action": (SPX, VIX, US10Y),
    "crypto": (DXY, VIX, SPX),
}

Quote = Callable[[str], tuple[float, float | None]]  # ticker → (dernier, clôture d'hier)


def yahoo_quote(ticker: str) -> tuple[float, float | None]:
    quote, daily = fetch(ticker, "1d", "5d")
    return quote.price, daily[-2].close if len(daily) >= 2 else None


def text(instrument: Instrument, quote: Quote = yahoo_quote) -> str:
    lines, prices = ["Marchés liés (Yahoo Finance, variation depuis la clôture d'hier) :"], {}
    for item in BY_KIND.get(instrument.kind, (DXY, VIX)):
        if item.ticker == instrument.yahoo:
            continue  # l'instrument lui-même : déjà dans le bloc marché
        try:
            last, previous = quote(item.ticker)
        except MarketUnavailable:
            lines.append(f"- {item.name} : indisponible")
            continue
        prices[item.key] = last
        if previous:
            change = (f"{last - previous:+.2f} point" if item.is_rate
                      else f"{(last / previous - 1) * 100:+.2f} %")  # fmt: skip
        else:
            change = "variation inconnue"
        lines.append(f"- {item.name} : {last:.2f} ({change})")
    gold, silver = prices.get("GOLD"), prices.get("SILVER")
    if instrument.kind == "metal" and silver:
        gold = gold or (yahoo_quote_safe(quote, GOLD.ticker))
        if gold:
            lines.append(f"- rapport or/argent : {gold / silver:.1f} (calcul sur le PC)")
    return "\n".join(lines)


def yahoo_quote_safe(quote: Quote, ticker: str) -> float | None:
    try:
        return quote(ticker)[0]
    except MarketUnavailable:
        return None
