"""Recherche de fichiers par leur nom, dans les dossiers autorisés.

Tolérante, car la demande vient souvent de la voix : accents et majuscules ignorés, petites
fautes acceptées, et les mois / années (« mon devis de mars 2025 ») peuvent correspondre à la
date de modification plutôt qu'au nom. Pas d'index : parcourir ~15 000 fichiers prend moins
d'une demi-seconde (la liste est gardée quelques secondes pour les recherches suivantes).
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from friday.voice.wake import normalize

KINDS = {
    "pdf": {".pdf"},
    "word": {".doc", ".docx", ".odt", ".rtf"},
    "excel": {".xls", ".xlsx", ".xlsm", ".csv", ".ods"},
    "powerpoint": {".ppt", ".pptx", ".odp"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp", ".tif", ".tiff"},
    "video": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "texte": {".txt", ".md"},
    "archive": {".zip", ".rar", ".7z"},
}
SKIP_DIRS = {
    "node_modules",
    "__pycache__",
    "site-packages",
    ".git",
    ".venv",
    "venv",
    "$recycle.bin",
}
MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}  # fmt: skip
STOP_WORDS = {
    "mon", "ma", "mes", "le", "la", "les", "de", "du", "des", "un", "une", "d", "l", "en",
    "fichier", "fichiers", "document", "documents", "dernier", "derniere", "derniers",
    "dernieres", "recent", "recents", "recente", "recentes",
}  # fmt: skip
# Mots qui désignent un type de fichier : un filtre, pas un mot à chercher dans le nom
KIND_WORDS = {
    "pdf": "pdf", "word": "word", "excel": "excel", "tableur": "excel",
    "powerpoint": "powerpoint", "photo": "image", "photos": "image", "image": "image",
    "images": "image", "video": "video", "videos": "video", "musique": "audio",
    "musiques": "audio", "zip": "archive",
}  # fmt: skip
FUZZY = 0.8  # ressemblance minimale d'un mot (« facure » ≈ « facture »)


@dataclass
class FileEntry:
    path: Path
    folder: str  # nom du dossier autorisé (« Documents »…)
    words: list[str]  # mots du nom, normalisés
    modified: datetime
    size: int


@dataclass
class Query:
    words: list[str]  # à trouver dans le nom
    month: int | None = None
    year: int | None = None

    @classmethod
    def parse(cls, text: str) -> "Query":
        query = cls([])
        for word in normalize(text).split():
            if word in MONTHS:
                query.month = MONTHS[word]
            elif len(word) == 4 and word.isdigit() and word[:2] in ("19", "20"):
                query.year = int(word)
            elif word not in STOP_WORDS:
                query.words.append(word)
        return query


def split_kind(text: str, kind: str | None) -> tuple[str, str | None]:
    """« mes derniers PDF » → (« mes derniers », « pdf ») : le type sort de la recherche."""
    found = normalize(kind or "") or None
    found = found if found in KINDS else None
    rest = []
    for word in normalize(text).split():
        if word in KIND_WORDS and found in (None, KIND_WORDS[word]):
            found = KIND_WORDS[word]
        else:
            rest.append(word)
    return " ".join(rest), found


def word_score(word: str, name_words: list[str], name: str) -> float:
    if word in name:  # « fact » dans « facture_edf »
        return 1.0
    if len(word) >= 4 and any(
        abs(len(w) - len(word)) <= 2 and SequenceMatcher(None, word, w).ratio() >= FUZZY
        for w in name_words
    ):
        return 0.7
    return 0.0


class FileFinder:
    def __init__(self, folders: dict[str, Path], cache_seconds: float = 30) -> None:
        self.folders = folders
        self.cache_seconds = cache_seconds
        self._cache: tuple[float, list[FileEntry]] | None = None

    def entries(self) -> list[FileEntry]:
        if self._cache and time.monotonic() - self._cache[0] < self.cache_seconds:
            return self._cache[1]
        found = [entry for name, root in self.folders.items() for entry in self._walk(name, root)]
        self._cache = (time.monotonic(), found)
        return found

    def _walk(self, folder: str, root: Path):
        """os.scandir : sous Windows, taille et date arrivent avec la liste (pas d'appel par
        fichier), 5 à 10 fois plus rapide qu'un stat() sur chaque fichier."""
        pending = [root]
        while pending:
            try:
                with os.scandir(pending.pop()) as items:
                    for item in items:
                        if item.is_dir(follow_symlinks=False):
                            name = item.name
                            if not name.startswith(".") and name.lower() not in SKIP_DIRS:
                                pending.append(Path(item.path))
                        elif item.is_file(follow_symlinks=False):
                            yield self._entry(folder, item)
            except OSError:  # dossier protégé ou disparu entre-temps
                continue

    @staticmethod
    def _entry(folder: str, item: os.DirEntry) -> FileEntry:
        stat = item.stat(follow_symlinks=False)
        path = Path(item.path)
        modified = datetime.fromtimestamp(stat.st_mtime)
        return FileEntry(path, folder, normalize(path.stem).split(), modified, stat.st_size)

    def find(self, text: str, kind: str | None = None, limit: int = 10) -> list[FileEntry]:
        query = Query.parse(text)
        extensions = KINDS.get(normalize(kind or ""))
        scored = []
        for entry in self.entries():
            if extensions and entry.path.suffix.lower() not in extensions:
                continue
            score = self._score(query, entry)
            if score is not None:
                scored.append((score, entry.modified, entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)  # puis le plus récent
        return [entry for _, _, entry in scored[:limit]]

    @staticmethod
    def _score(query: Query, entry: FileEntry) -> float | None:
        """None : le fichier ne correspond pas. Sinon, plus c'est haut, mieux c'est."""
        name = " ".join(entry.words)
        scores = [word_score(w, entry.words, name) for w in query.words]
        matched = sum(1 for s in scores if s)
        if query.words and matched < max(1, round(len(query.words) * 2 / 3)):
            return None
        score = sum(scores)
        for value, months_or_years in ((query.month, MONTHS), (query.year, None)):
            if value is None:
                continue
            date_value = entry.modified.month if months_or_years else entry.modified.year
            in_name = str(value) in name.split() or (
                months_or_years and any(MONTHS.get(w) == value for w in entry.words)
            )
            if date_value == value or in_name:
                score += 1
            elif not query.words:  # « mes PDF de mars » : la date est le seul critère
                return None
        return score
