"""Les instruments suivis : devises, métaux, matières premières, indices, crypto, actions.

Chaque fiche dit comment le reconnaître (« l'or », « XAUUSD », « EUR/USD »), où trouver ses
cours (symbole Yahoo), la taille d'un pip / point et d'un contrat (pour les calculs de risque),
et les devises dont l'actualité le fait bouger (calendrier économique).

On change d'instrument en le nommant (« et sur l'or ? ») ou en changeant de graphique dans
TradingView (son titre commence par le symbole). Un symbole inconnu est traité comme une
action (« AAPL », « MC.PA »).
"""

import re
from dataclasses import dataclass

from friday.voice.wake import normalize


@dataclass(frozen=True)
class Instrument:
    symbol: str  # « EURUSD », « XAUUSD », « AAPL »
    name: str  # pour parler : « EUR/USD », « l'or »
    kind: str  # forex, metal, energie, indice, crypto, action
    yahoo: str  # symbole des cours chez Yahoo
    pip: float  # un pip (forex) ou un point (le reste), en devise de cotation
    contract: float  # unités par lot (100 000 devises, 100 onces d'or…)
    quote: str  # devise de cotation (USD, JPY…)
    currencies: tuple[str, ...]  # devises dont le calendrier compte
    note: str = ""  # précision sur la source (contrat à terme…)

    @property
    def label(self) -> str:
        return f"{self.name} ({self.symbol})"


MAJORS = ("EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
CURRENCY_NAMES = {
    "EUR": "euro", "USD": "dollar", "GBP": "livre", "JPY": "yen", "CHF": "franc suisse",
    "CAD": "dollar canadien", "AUD": "dollar australien", "NZD": "dollar néo-zélandais",
}  # fmt: skip


def forex(base: str, quote: str) -> Instrument:
    return Instrument(
        f"{base}{quote}", f"{base}/{quote}", "forex", f"{base}{quote}=X",
        0.01 if quote == "JPY" else 0.0001, 100_000, quote, (base, quote),
    )  # fmt: skip


FUTURES = "cours d'un contrat à terme (très proche du comptant)"
OTHERS = {
    "XAUUSD": Instrument("XAUUSD", "l'or", "metal", "GC=F", 0.1, 100, "USD", ("USD",), FUTURES),
    "XAGUSD": Instrument("XAGUSD", "l'argent (métal)", "metal", "SI=F", 0.01, 5000, "USD",
                         ("USD",), FUTURES),
    "USOIL": Instrument("USOIL", "le pétrole WTI", "energie", "CL=F", 0.01, 1000, "USD",
                        ("USD",), FUTURES),
    "UKOIL": Instrument("UKOIL", "le pétrole Brent", "energie", "BZ=F", 0.01, 1000, "USD",
                        ("USD",), FUTURES),
    "SPX": Instrument("SPX", "le S&P 500", "indice", "^GSPC", 1, 1, "USD", ("USD",)),
    "NDX": Instrument("NDX", "le Nasdaq 100", "indice", "^NDX", 1, 1, "USD", ("USD",)),
    "DAX": Instrument("DAX", "le DAX", "indice", "^GDAXI", 1, 1, "EUR", ("EUR",)),
    "CAC40": Instrument("CAC40", "le CAC 40", "indice", "^FCHI", 1, 1, "EUR", ("EUR",)),
    "BTCUSD": Instrument("BTCUSD", "le bitcoin", "crypto", "BTC-USD", 1, 1, "USD", ("USD",)),
    "ETHUSD": Instrument("ETHUSD", "l'ether", "crypto", "ETH-USD", 0.01, 1, "USD", ("USD",)),
}  # fmt: skip
# Autres noms des fiches (Yahoo, courtiers, TradingView)
SYMBOL_ALIASES = {
    "GOLD": "XAUUSD", "GC1!": "XAUUSD", "SILVER": "XAGUSD", "SI1!": "XAGUSD",
    "WTI": "USOIL", "CL1!": "USOIL", "USOUSD": "USOIL", "BRENT": "UKOIL", "UKOUSD": "UKOIL",
    "SPX500": "SPX", "US500": "SPX", "NAS100": "NDX", "US100": "NDX", "GER40": "DAX",
    "DE40": "DAX", "FRA40": "CAC40", "FR40": "CAC40", "BTCUSDT": "BTCUSD", "ETHUSDT": "ETHUSD",
    # noms dits en français (le modèle les passe tels quels aux outils)
    "OR": "XAUUSD", "ARGENT": "XAGUSD", "PETROLE": "USOIL", "PÉTROLE": "USOIL",
    "BITCOIN": "BTCUSD", "ETHER": "ETHUSD", "ETHEREUM": "ETHUSD", "NASDAQ": "NDX",
}  # fmt: skip
# Comment on les dit (texte normalisé, sans accents)
SPOKEN = {
    "XAUUSD": ("l or", "gold", "once d or", "xau"),
    "XAGUSD": ("silver", "argent metal", "cours de l argent", "sur l argent", "xag"),
    "USOIL": ("petrole", "wti", "baril"),
    "UKOIL": ("brent",),
    "SPX": ("s p 500", "sp500", "s and p"),
    "NDX": ("nasdaq",),
    "DAX": ("dax",),
    "CAC40": ("cac 40", "cac40"),
    "BTCUSD": ("bitcoin", "btc"),
    "ETHUSD": ("ether", "ethereum"),
}  # fmt: skip
# Devise d'une action selon le suffixe de sa bourse chez Yahoo (sans suffixe : États-Unis)
EXCHANGE_CURRENCY = {
    "PA": "EUR", "DE": "EUR", "F": "EUR", "AS": "EUR", "MI": "EUR", "MC": "EUR", "BR": "EUR",
    "L": "GBP", "T": "JPY", "SW": "CHF", "TO": "CAD", "AX": "AUD",
}  # fmt: skip
_PAIR = re.compile(r"\b(" + "|".join(MAJORS) + r")\s*[/ -]?\s*(" + "|".join(MAJORS) + r")\b", re.I)


def by_symbol(symbol: str) -> Instrument | None:
    """Fiche d'un symbole (« EURUSD », « OANDA:XAUUSD », « GOLD », « AAPL »)."""
    raw = symbol.strip().upper().split(":")[-1].replace("/", "").replace(" ", "")
    raw = SYMBOL_ALIASES.get(raw, raw)
    if raw in OTHERS:
        return OTHERS[raw]
    if len(raw) == 6 and raw[:3] in MAJORS and raw[3:] in MAJORS and raw[:3] != raw[3:]:
        return forex(raw[:3], raw[3:])
    if re.fullmatch(r"[A-Z][A-Z0-9]{0,5}(\.[A-Z]{1,3})?", raw):
        currency = EXCHANGE_CURRENCY.get(raw.rpartition(".")[2] if "." in raw else "", "USD")
        return Instrument(raw, raw, "action", raw, 0.01, 1, currency, (currency,))
    return None


def detect(text: str) -> Instrument | None:
    """L'instrument dont parle la phrase, ou None (« et sur l'or ? », « EUR/USD », « cable »)."""
    padded = f" {normalize(text)} "
    for symbol, words in SPOKEN.items():
        if any(f" {w} " in padded for w in words):  # mots entiers (« l or », pas « l orage »)
            return OTHERS[symbol]
    pair = _PAIR.search(text)
    if pair and pair.group(1).upper() != pair.group(2).upper():
        return forex(pair.group(1).upper(), pair.group(2).upper())
    for word in re.findall(r"\b[A-Z][A-Z0-9:!.]{2,11}\b", text):  # symbole écrit en capitales
        found = by_symbol(word)
        if found and found.kind != "action":  # « RSI », « ATR » ne sont pas des actions
            return found
    stock = re.search(r"\bactions?\s+(?:de\s+|d')?([A-Z][A-Z0-9]{0,5}(?:\.[A-Z]{1,3})?)\b", text)
    return by_symbol(stock.group(1)) if stock else None


def parse_price(text: str) -> float | None:
    """« 4 163,210 », « 1,12585 », « 4,163.21 », « 98 765,4 » → nombre (formats FR et EN)."""
    raw = re.sub(r"[\s\u00a0\u202f]", "", text)
    if "," in raw and "." in raw:  # « 4,163.21 » : la virgule sépare les milliers
        raw = raw.replace(",", "")
    raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def chart_price(title: str, instrument: Instrument) -> float | None:
    """Le cours affiché par le graphique TradingView, s'il montre bien cet instrument
    (« XAUUSD 4 163,210 ▼ −0.02% » : le cours exact du graphique de l'utilisateur)."""
    shown = from_chart_title(title)
    if shown is None or shown.symbol != instrument.symbol:
        return None
    found = re.match(r"^\S+\s+(\d[\d\s\u00a0\u202f.,]*\d)", title.strip())
    return parse_price(found.group(1)) if found else None


def from_chart_title(title: str) -> Instrument | None:
    """Le symbole en tête du titre TradingView (« XAUUSD 4 192,7 ▲ +0.4% - Google Chrome »)."""
    first = title.strip().split(" ")[0] if title.strip() else ""
    return by_symbol(first) if first else None
