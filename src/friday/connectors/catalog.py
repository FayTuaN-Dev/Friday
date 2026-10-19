"""Les connecteurs tout prêts, proposés dans Réglages → Connecteurs → Ajouter : leur entrée
de data/mcp.json, déjà réglée (adresse, mots-clés, outils légers pour qwen)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preset:
    name: str
    note: str  # ce qu'il faut savoir avant (compte, offre, logiciel)
    entry: dict = field(hash=False)


PRESETS = (
    Preset("notion", "Tes pages Notion : chercher, lire, créer. Compte Notion (gratuit) : "
           "« Se connecter » après l'ajout.", {
               "url": "https://mcp.notion.com/mcp",
               "description": "mes pages Notion",
               "mots_cles": ["notion"],
               "outils": ["notion-search", "notion-fetch", "notion-list-recent-pages",
                          "notion-list-favorite-pages", "notion-create-pages",
                          "notion-get-comments"],
           }),
    Preset("heure", "L'heure partout dans le monde et les conversions de fuseaux. Rien à "
           "régler (le programme s'installe tout seul au premier branchement).", {
               "commande": "uvx",
               "arguments": ["mcp-server-time", "--local-timezone=Europe/Paris"],
               "description": "l'heure dans le monde et les conversions de fuseaux horaires",
               "mots_cles": ["fuseau", "heure a", "heure au", "heure en"],
           }),
    Preset("alphavantage", "Marchés pour ton trading : or et argent au comptant, devises, "
           "actions, actualités et sentiment, CPI, NFP, taux de la Fed. Compte gratuit "
           "(25 demandes par jour) : « Se connecter » après l'ajout.", {
               "url": "https://mcp.alphavantage.co/mcp",
               "description": "données de marché Alpha Vantage : or au comptant, devises, "
                              "actions, actualités et sentiment, inflation, emploi, taux",
               "mots_cles": ["alpha", "comptant", "spot", "sentiment", "cpi", "nfp",
                             "inflation", "taux de la fed"],
               "outils": ["GOLD_SILVER_SPOT", "CURRENCY_EXCHANGE_RATE", "FX_DAILY",
                          "GLOBAL_QUOTE", "SYMBOL_SEARCH", "NEWS_SENTIMENT", "CPI",
                          "NONFARM_PAYROLL", "FEDERAL_FUNDS_RATE"],
           }),
    Preset("coingecko", "Les cryptos (cours, capitalisation, tendances), sans compte. "
           "Expérimental : Friday y écrit un petit programme à chaque question, qwen peut "
           "s'y tromper.", {
               "url": "https://mcp.api.coingecko.com/mcp",
               "description": "les cryptomonnaies CoinGecko : cours, capitalisation, tendances",
               "mots_cles": ["coingecko", "crypto"],
           }),
    Preset("tradingview", "Données de marché TradingView (cours, screener, actualités, "
           "calendrier). Demande l'offre Essential ou plus ; « Se connecter » après l'ajout.", {
               "url": "https://mcp.tradingview.com/mcp",
               "description": "les données de marché TradingView (cours, analyse technique, "
                              "actualités, calendrier économique)",
               "mots_cles": ["tradingview"],
           }),
)  # fmt: skip
