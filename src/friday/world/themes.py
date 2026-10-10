"""Ce qui relie l'actualité internationale aux marchés (J9) : des thèmes (Moyen-Orient,
Russie et Ukraine, Fed…), leurs mots dans les titres, et les instruments qu'ils font bouger
d'habitude. Une grille de lecture fixe, écrite à la main : ni un signal, ni un conseil."""

from dataclasses import dataclass

from friday.trading.instruments import Instrument
from friday.voice.wake import normalize


@dataclass(frozen=True)
class Theme:
    name: str
    words: tuple[str, ...]  # débuts de mots, sans accents
    symbols: tuple[str, ...]  # instruments touchés
    currencies: tuple[str, ...]  # devises touchées
    moves: str  # pour le dire : « le pétrole et l'or »

    def concerns(self, instrument: Instrument) -> bool:
        """Le dollar ne compte que pour les paires de devises (tout est coté en dollars)."""
        if instrument.symbol in self.symbols:
            return True
        shared = set(instrument.currencies) & set(self.currencies)
        return bool(shared - {"USD"}) or (bool(shared) and instrument.kind == "forex")


THEMES = (
    Theme("Moyen-Orient", ("iran", "israel", "gaza", "liban", "hezbollah", "hamas", "houthi",
                           "yemen", "arabie saoudite", "golfe persique", "ormuz", "syrie", "irak"),
          ("USOIL", "UKOIL", "XAUUSD"), (), "le pétrole et l'or"),
    Theme("pétrole et OPEP", ("opep", "opec", "petrol", "baril", "brent", "raffiner"),
          ("USOIL", "UKOIL", "USDCAD"), ("CAD",), "le pétrole"),
    Theme("Russie et Ukraine", ("russ", "ukrain", "poutine", "kremlin", "zelensky", "moscou",
                                "kiev", "kyiv", "zaporij"),
          ("EURUSD", "XAUUSD", "UKOIL"), ("EUR",), "l'euro, l'or et l'énergie"),
    Theme("Chine et Taïwan", ("chine", "chinois", "pekin", "taiwan", "xi jinping"),
          ("AUDUSD", "XAUUSD"), ("AUD",), "le dollar australien et l'or"),
    Theme("Fed et dollar", ("fed ", "reserve federale", "powell", "tresor americain"),
          ("XAUUSD",), ("USD",), "le dollar et l'or"),
    Theme("BCE et zone euro", ("bce", "lagarde", "zone euro", "eurozone"), (), ("EUR",),
          "l'euro"),
    Theme("commerce mondial", ("droits de douane", "douanier", "guerre commerciale", "tarifs",
                               "embargo", "sanctions"),
          ("XAUUSD",), ("USD",), "le dollar et l'or"),
    Theme("Japon", ("japon", "japonais", "tokyo", "banque du japon"), (), ("JPY",), "le yen"),
    Theme("Royaume-Uni", ("royaume uni", "britanni", "londres", "banque d angleterre",
                          "starmer"), (), ("GBP",), "la livre sterling"),
    Theme("politique américaine", ("trump", "maison blanche", "congres americain", "shutdown"),
          ("XAUUSD",), ("USD",), "le dollar et l'or"),
)  # fmt: skip
BY_NAME = {t.name: t for t in THEMES}
# Où placer chaque thème sur le globe (J9b) : (latitude, longitude)
CENTERS = {"Moyen-Orient": (29.5, 47.5), "pétrole et OPEP": (24.5, 54.0),
           "Russie et Ukraine": (49.0, 33.0), "Chine et Taïwan": (28.0, 116.0),
           "Fed et dollar": (40.7, -74.0), "BCE et zone euro": (50.1, 8.7),
           "commerce mondial": (46.2, 6.1), "Japon": (35.7, 139.7),
           "Royaume-Uni": (51.5, -0.1), "politique américaine": (38.9, -77.0)}  # fmt: skip
# Catastrophes (pays GDACS, en anglais) → le thème qu'elles touchent
DISASTER_THEMES = {"Japan": "Japon", "Iran": "Moyen-Orient", "Saudi Arabia": "Moyen-Orient",
                   "Iraq": "Moyen-Orient", "United Arab Emirates": "Moyen-Orient",
                   "China": "Chine et Taïwan", "Taiwan": "Chine et Taïwan",
                   "Russia": "Russie et Ukraine", "Ukraine": "Russie et Ukraine",
                   "United Kingdom": "Royaume-Uni"}  # fmt: skip
# Cyclones dans le golfe du Mexique (plateformes et raffineries) : touchent le pétrole
GULF_OF_MEXICO = ((18.0, 31.0), (-98.0, -80.0))  # (latitudes, longitudes)
COUNTRIES = {
    "Japan": "au Japon", "China": "en Chine", "Taiwan": "à Taïwan", "Indonesia": "en Indonésie",
    "Philippines": "aux Philippines", "United States": "aux États-Unis", "Mexico": "au Mexique",
    "Cuba": "à Cuba", "Haiti": "en Haïti", "Chile": "au Chili", "Peru": "au Pérou",
    "Ecuador": "en Équateur", "Colombia": "en Colombie", "Panama": "au Panama",
    "Guatemala": "au Guatemala", "Brazil": "au Brésil", "Argentina": "en Argentine",
    "Canada": "au Canada", "India": "en Inde", "Pakistan": "au Pakistan",
    "Bangladesh": "au Bangladesh", "Nepal": "au Népal", "Afghanistan": "en Afghanistan",
    "Iran": "en Iran", "Iraq": "en Irak", "Turkey": "en Turquie", "Greece": "en Grèce",
    "Italy": "en Italie", "France": "en France", "Spain": "en Espagne", "Portugal": "au Portugal",
    "Russia": "en Russie", "Ukraine": "en Ukraine", "Vietnam": "au Viêt Nam",
    "Viet Nam": "au Viêt Nam", "Thailand": "en Thaïlande", "Myanmar": "en Birmanie",
    "Malaysia": "en Malaisie", "Papua New Guinea": "en Papouasie-Nouvelle-Guinée",
    "New Zealand": "en Nouvelle-Zélande", "Australia": "en Australie", "Tonga": "aux Tonga",
    "Vanuatu": "au Vanuatu", "Fiji": "aux Fidji", "Morocco": "au Maroc", "Algeria": "en Algérie",
    "Nigeria": "au Nigeria", "Ethiopia": "en Éthiopie", "Kenya": "au Kenya",
    "Somalia": "en Somalie", "Madagascar": "à Madagascar", "Mozambique": "au Mozambique",
    "South Africa": "en Afrique du Sud", "Iceland": "en Islande",
    "Saudi Arabia": "en Arabie saoudite",
    "South Korea": "en Corée du Sud", "Korea, Republic of": "en Corée du Sud",
}  # fmt: skip


def themes_of(text: str) -> list[Theme]:
    padded = f" {normalize(text)} "
    return [t for t in THEMES if any(f" {w}" in padded for w in t.words)]


def where(country: str) -> str:
    """« au Japon » ; un pays inconnu reste en anglais, en mer : « en mer »."""
    if not country:
        return "en mer"
    return COUNTRIES.get(country, f"({country})")


def disaster_theme(disaster) -> Theme | None:
    (south, north), (west, east) = GULF_OF_MEXICO
    if disaster.kind == "TC" and south <= disaster.lat <= north and west <= disaster.lon <= east:
        return BY_NAME["pétrole et OPEP"]
    name = DISASTER_THEMES.get(disaster.country)
    return BY_NAME[name] if name else None
