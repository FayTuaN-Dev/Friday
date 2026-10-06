"""Outil : le cours d'un instrument (devise, or, argent, pétrole, indice, crypto, action), lu à
la source plutôt que dans des extraits de recherche web (souvent périmés ou inversés :
constaté, « le cours de l'euro dollar » donnait 0,91, 1,03 ou 1,12 selon les essais)."""

from friday.tools.base import Tool, ToolResult
from friday.trading.instruments import by_symbol, detect
from friday.trading.market import MarketUnavailable, fetch
from friday.trading.reference_rates import RatesUnavailable, reference_rate


class MarketQuoteTool(Tool):
    name = "market_quote"
    description = (
        "Cours actuel d'une devise, de l'or, de l'argent, du pétrole, d'un indice, d'une crypto "
        "ou d'une action (« combien vaut l'euro en dollars ? », « le prix de l'or »). Toujours "
        "cet outil pour un cours, jamais la recherche web."
    )
    parameters = {
        "instrument": {"type": "string",
                       "description": "« EUR/USD », « or », « argent », « bitcoin », « AAPL »…"}
    }  # fmt: skip
    required = ("instrument",)

    def label(self, args: dict) -> str:
        return f"💱 Cours : {args.get('instrument', '')}"

    def run(self, instrument: str) -> ToolResult:
        item = detect(instrument) or by_symbol(instrument)
        if item is None:
            return ToolResult(f"Instrument inconnu : « {instrument} ». Demande lequel.")
        try:
            quote, daily = fetch(item.yahoo, "1d", "5d")
        except MarketUnavailable as error:
            return ToolResult(f"{error} Dis-le simplement.")
        change = ""
        if len(daily) >= 2 and daily[-2].close:
            change = f" ({(quote.price / daily[-2].close - 1) * 100:+.2f} % depuis hier)"
        text = (
            f"Cours — {item.label} : {quote.price:g} {quote.currency or item.quote}{change}, "
            f"à {quote.time:%d/%m %H:%M} UTC (Yahoo Finance"
            + (f", {item.note}" if item.note else "")
            + ")."
        )
        if item.kind == "forex":
            base, quoted = item.symbol[:3], item.symbol[3:]
            try:
                rate, day = reference_rate(base, quoted)
                text += f" Cours de référence BCE du {day} : {rate:g}."
            except RatesUnavailable:
                pass
        return ToolResult(text + " Donne ces chiffres tels quels, avec l'heure.")
