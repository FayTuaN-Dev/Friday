"""Bibliothèque de trading de départ : UNIQUEMENT des documents légalement gratuits,
téléchargés pour un usage personnel, chacun avec sa source et sa licence en tête de fichier.

- Wikipédia en français : licence CC BY-SA 4.0 (citer la source).
- Régulateurs et banques centrales (AMF, Banque de France, BRI) : documents publiés
  gratuitement pour le public ; copie personnelle, pas de redistribution.
- Réserve fédérale américaine : œuvre du gouvernement fédéral, domaine public.

Les livres protégés ne sont PAS téléchargés (les PDF « gratuits » de livres connus sont presque
toujours piratés) : voir docs/livres-trading.md, à acheter puis déposer dans la bibliothèque.
"""

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

FOLDER = "trading"  # sous-dossier de data/bibliotheque
USER_AGENT = "Friday-assistant/1.0 (https://github.com/FayTuaN-Dev/Friday; usage personnel)"
WIKIPEDIA_API = "https://fr.wikipedia.org/w/api.php"
PAUSE = 1.0  # secondes entre deux téléchargements (Wikipédia demande de ne pas insister)
WIKI_LICENSE = "Wikipédia (fr), licence CC BY-SA 4.0"


@dataclass(frozen=True)
class Source:
    title: str
    kind: str  # « wikipedia », « pdf » ou « page »
    ref: str  # titre de l'article, ou adresse
    publisher: str
    license: str

    @property
    def filename(self) -> str:
        name = re.sub(r"[^\w\s-]", "", self.title, flags=re.UNICODE).strip().replace(" ", "_")
        return f"{name}.{'pdf' if self.kind == 'pdf' else 'md'}"


def _wiki(title: str) -> Source:
    return Source(f"Wikipédia - {title}", "wikipedia", title, "Wikipédia", WIKI_LICENSE)


CATALOG = (
    *(_wiki(t) for t in (
        "Forex", "Taux de change", "Parité des taux d'intérêt", "Carry trade",
        "Politique monétaire", "Banque centrale européenne", "Réserve fédérale des États-Unis",
        "Analyse technique", "Chandeliers japonais", "Figures chartistes", "Moyenne mobile",
        "Relative strength index", "MACD", "Bandes de Bollinger", "Théorie de Dow",
        "Théorie des vagues d'Elliott", "Effet de levier", "Contrat de différence", "Spread",
        "Volatilité (finance)", "Finance comportementale", "Valeur refuge", "Étalon-or",
        "Prix du pétrole", "Organisation des pays exportateurs de pétrole", "Matière première",
        "Inflation", "Taux directeur",
    )),
    Source("AMF - Forex attention danger (2023)", "pdf",
           "https://www.amf-france.org/sites/institutionnel/files/private/2023-12/"
           "2023_forex_attention_danger.pdf",
           "Autorité des marchés financiers", "publication gratuite de l'AMF, usage personnel"),
    Source("AMF - Etude sur les particuliers et le Forex (2014)", "pdf",
           "https://www.amf-france.org/sites/institutionnel/files/contenu_simple/lettre_ou_cahier/"
           "lettre_observatoire/La%20lettre%20de%20l%27Observatoire%20de%20l%27epargne%20de%20"
           "l%27AMF%20-%20ndeg%2010%20-%20Octobre%202014.pdf",
           "Autorité des marchés financiers", "publication gratuite de l'AMF, usage personnel"),
    Source("Banque de France - Le taux de change", "page",
           "https://abc-economie.banque-france.fr/le-taux-de-change",
           "Banque de France", "fiche pédagogique gratuite, usage personnel"),
    Source("Federal Reserve - The Fed Explained", "pdf",
           "https://www.federalreserve.gov/aboutthefed/files/the-fed-explained.pdf",
           "Board of Governors of the Federal Reserve System", "domaine public (États-Unis)"),
    Source("BRI - Enquete triennale sur le marche des changes (2022)", "page",
           "https://www.bis.org/statistics/rpfx22.htm",
           "Banque des règlements internationaux",
           "publication gratuite de la BRI, usage personnel"),
)  # fmt: skip


def _header(source: Source, url: str) -> str:
    return (f"# {source.title}\n\nSource : {source.publisher} — {url}\nLicence : "
            f"{source.license}\n\n")  # fmt: skip


def download(source: Source, get=httpx.get) -> bytes:
    """Le contenu du document (Markdown, ou PDF brut)."""
    headers = {"User-Agent": USER_AGENT}
    if source.kind == "wikipedia":
        response = get(WIKIPEDIA_API, params={
            "action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
            "format": "json", "titles": source.ref}, headers=headers, timeout=30)  # fmt: skip
        response.raise_for_status()
        page = next(iter(response.json()["query"]["pages"].values()))
        text = page.get("extract") or ""
        if len(text) < 500:
            raise ValueError("article introuvable ou trop court")
        url = "https://fr.wikipedia.org/wiki/" + page["title"].replace(" ", "_")
        return (_header(source, url) + text).encode("utf-8")
    response = get(source.ref, headers=headers, timeout=60, follow_redirects=True)
    response.raise_for_status()
    if source.kind == "pdf":
        if not response.content.startswith(b"%PDF"):
            raise ValueError("ce n'est pas un PDF")
        return response.content
    import trafilatura

    text = trafilatura.extract(response.text) or ""
    if len(text) < 300:
        raise ValueError("page sans contenu lisible")
    return (_header(source, source.ref) + text).encode("utf-8")


def fetch_catalog(
    library_folder: Path, get=httpx.get, pause: Callable[[float], None] = time.sleep,
    on_progress: Callable[[str], None] = lambda title: None,
) -> dict[str, list[str]]:  # fmt: skip
    """Télécharge ce qui manque dans data/bibliotheque/trading (déjà là : ignoré)."""
    folder = library_folder / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    report: dict[str, list[str]] = {"added": [], "present": [], "failed": []}
    for source in CATALOG:
        target = folder / source.filename
        if target.exists():
            report["present"].append(source.title)
            continue
        on_progress(source.title)
        try:
            target.write_bytes(download(source, get))
            report["added"].append(source.title)
        except (httpx.HTTPError, ValueError, KeyError, StopIteration) as error:
            log.warning("Bibliothèque de trading : %s indisponible (%s)", source.title, error)
            report["failed"].append(f"{source.title} ({error})")
        pause(PAUSE)
    return report
