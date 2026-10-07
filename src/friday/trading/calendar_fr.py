"""Les annonces économiques courantes en français (ForexFactory les donne en anglais). Les
titres inconnus restent en anglais : mieux vaut l'original qu'une traduction inventée."""

# Du plus précis au plus général : « Core CPI m/m » avant « CPI m/m »
NAMES = (
    ("Non-Farm Employment Change", "créations d'emplois non agricoles (NFP)"),
    ("ADP Non-Farm Employment Change", "créations d'emplois privés ADP"),
    ("Unemployment Claims", "inscriptions hebdomadaires au chômage"),
    ("Unemployment Rate", "taux de chômage"),
    ("Average Hourly Earnings", "salaire horaire moyen"),
    ("JOLTS Job Openings", "offres d'emploi JOLTS"),
    ("Core CPI", "inflation sous-jacente (CPI hors énergie et alimentation)"),
    ("CPI", "inflation (indice des prix à la consommation)"),
    ("Core PPI", "prix à la production sous-jacents"),
    ("PPI", "prix à la production"),
    ("Core PCE Price Index", "inflation PCE sous-jacente"),
    ("Federal Funds Rate", "décision de taux de la Fed"),
    ("FOMC Statement", "communiqué de la Fed"),
    ("FOMC Press Conference", "conférence de presse de la Fed"),
    ("FOMC Meeting Minutes", "compte rendu de la Fed"),
    ("Fed Chair", "discours du président de la Fed"),
    ("Main Refinancing Rate", "décision de taux de la BCE"),
    ("ECB Press Conference", "conférence de presse de la BCE"),
    ("ECB President", "discours de la présidente de la BCE"),
    ("Official Bank Rate", "décision de taux de la Banque d'Angleterre"),
    ("BOJ Policy Rate", "décision de taux de la Banque du Japon"),
    ("Advance GDP", "croissance du PIB (première estimation)"),
    ("Prelim GDP", "croissance du PIB (estimation préliminaire)"),
    ("GDP", "croissance du PIB"),
    ("Core Retail Sales", "ventes au détail hors automobile"),
    ("Retail Sales", "ventes au détail"),
    ("ISM Manufacturing PMI", "indice ISM manufacturier"),
    ("ISM Services PMI", "indice ISM des services"),
    ("Flash Manufacturing PMI", "PMI manufacturier (première estimation)"),
    ("Flash Services PMI", "PMI des services (première estimation)"),
    ("Manufacturing PMI", "PMI manufacturier"),
    ("Services PMI", "PMI des services"),
    ("Prelim UoM Consumer Sentiment", "confiance des consommateurs (Michigan)"),
    ("CB Consumer Confidence", "confiance des consommateurs (Conference Board)"),
    ("Crude Oil Inventories", "stocks de pétrole brut"),
    ("Durable Goods Orders", "commandes de biens durables"),
    ("Trade Balance", "balance commerciale"),
    ("German Prelim CPI", "inflation allemande (estimation)"),
    ("ZEW Economic Sentiment", "moral des investisseurs ZEW"),
    ("Ifo Business Climate", "climat des affaires Ifo"),
    ("Bank Holiday", "jour férié"),
)
PERIODS = {"m/m": "sur un mois", "y/y": "sur un an", "q/q": "sur un trimestre"}


def french(title: str) -> str:
    """« Core CPI m/m » → « inflation sous-jacente (…) sur un mois »."""
    for english, name in NAMES:
        if title.startswith(english):
            rest = title[len(english) :].removesuffix("Speaks").strip()  # « Powell Speaks »
            period = PERIODS.get(rest)
            if period:
                return f"{name} {period}"
            return name if not rest else f"{name} ({rest})"
    return title
