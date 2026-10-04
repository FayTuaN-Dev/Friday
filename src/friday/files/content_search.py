"""Recherche de mots DANS les documents (PDF, Word, texte) : plus lente, donc en option,
limitée dans le temps, et en commençant par les fichiers les plus récents."""

import logging
import time

from friday.files.readers import SUPPORTED, UnreadableFile, read_document
from friday.files.search import STOP_WORDS, FileEntry
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024  # au-delà, trop long à lire pour une recherche
TIME_BUDGET = 10.0  # secondes


def search_contents(
    entries: list[FileEntry], text: str, limit: int = 10, budget: float = TIME_BUDGET
) -> tuple[list[FileEntry], bool]:
    """Fichiers dont le texte contient tous les mots. Le booléen indique si la recherche a
    été interrompue faute de temps (certains fichiers n'ont pas été lus)."""
    words = [w for w in normalize(text).split() if w not in STOP_WORDS]
    if not words:
        return [], False
    candidates = [e for e in entries if e.path.suffix.lower() in SUPPORTED and e.size <= MAX_BYTES]
    candidates.sort(key=lambda e: e.modified, reverse=True)
    deadline = time.monotonic() + budget
    found = []
    for entry in candidates:
        if time.monotonic() > deadline:
            return found, True
        try:
            content = normalize(read_document(entry.path).text)
        except (UnreadableFile, OSError, ValueError) as error:
            log.debug("Contenu illisible %s : %s", entry.path, error)
            continue
        except Exception:  # un PDF exotique ne doit pas arrêter la recherche
            log.debug("Échec de lecture de %s", entry.path, exc_info=True)
            continue
        if all(w in content for w in words):
            found.append(entry)
            if len(found) >= limit:
                break
    return found, False
