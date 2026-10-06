"""La bibliothèque de Friday : les documents du dossier data/bibliotheque, découpés en passages
et indexés, pour répondre à partir d'eux plutôt que de chercher sur internet.

Recherche hybride : par le sens (embeddings, même petit modèle que la mémoire, sur CPU) ET
par les mots exacts (FTS5), fusionnées par rang (RRF). Seuls les meilleurs passages vont au
modèle : quelques centaines de jetons au lieu d'un livre entier.
"""

import logging
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

from friday.files.readers import SUPPORTED, UnreadableFile, read_document
from friday.library.chunker import split
from friday.library.store import Hit, LibraryStore
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

CANDIDATES = 20  # par méthode, avant fusion
RRF_K = 60  # constante habituelle de la fusion par rang
# Mesuré sur de vrais articles : questions en rapport 0,47–0,61 ; hors sujet 0,10–0,33.
MIN_SIMILARITY = 0.40
CLOSE_TO_BEST = 0.12  # écart toléré avec le meilleur passage
EMBED_BATCH = 16
RETIRED = "_retires"  # « retirer » un document le déplace ici : rien n'est effacé
# Questions sur le présent : un livre n'a pas la réponse (constaté : « le cours de l'euro
# aujourd'hui » → un exemple du guide donné comme cours actuel). Internet, pas la bibliothèque.
# Préfixes (« aujourd » : résiste à « aujourdh'ui », faute réelle).
NOW = (
    " aujourd", " auj ", " actuel", " en ce moment", " maintenant", " ce matin", " ce soir",
    " hier", " cette semaine", " ce mois", " dernieres nouvelles", " actualite", " news",
    " en direct", " a l instant", " recemment", " derniere minute",
    # un cours, un prix : toujours le présent (le livre n'a que des exemples)
    " cours de l", " cours du ", " cours des ", " combien vaut", " combien coute",
    " prix du ", " prix de l", " taux de change actuel",
)  # fmt: skip


def about_now(question: str) -> bool:
    padded = f" {normalize(question)} "
    return any(word in padded for word in NOW)


class Library:
    def __init__(self, folder: Path, store: LibraryStore, embedder) -> None:
        self.folder = folder
        self.store = store
        self.embedder = embedder
        self._sync_lock = threading.Lock()
        self.indexing: str | None = None  # document en cours d'indexation (pour l'affichage)
        self._known: tuple[str, list[str]] = ("", [])
        folder.mkdir(parents=True, exist_ok=True)

    # --- indexation -------------------------------------------------------------------------

    def files(self) -> list[Path]:
        return sorted(
            p for p in self.folder.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED and RETIRED not in p.parts
        )  # fmt: skip

    def sync(self, on_change: Callable[[], None] = lambda: None) -> dict[str, list[str]]:
        """Indexe les nouveaux fichiers et ceux modifiés, oublie ceux disparus."""
        report: dict[str, list[str]] = {"added": [], "removed": [], "failed": []}
        with self._sync_lock:
            known = {d.path: d for d in self.store.documents()}
            present = {str(p): p for p in self.files()}
            for path in set(known) - set(present):
                self.store.remove(path)
                report["removed"].append(Path(path).name)
            for key, path in present.items():
                mtime = path.stat().st_mtime
                if key in known and abs(known[key].mtime - mtime) < 1:
                    continue
                try:
                    self._index(path, mtime)
                    report["added"].append(path.name)
                except UnreadableFile as error:
                    log.warning("Bibliothèque : %s", error)
                    report["failed"].append(f"{path.name} : {error}")
                except Exception:  # un fichier ne doit pas bloquer les autres
                    log.exception("Bibliothèque : indexation de %s impossible", path.name)
                    report["failed"].append(path.name)
                finally:
                    self.indexing = None
                on_change()
        if any(report.values()):
            log.info("Bibliothèque : %s", {k: len(v) for k, v in report.items()})
        return report

    def sync_in_background(self, on_change: Callable[[], None] = lambda: None) -> None:
        threading.Thread(target=self.sync, args=(on_change,), daemon=True).start()

    def _index(self, path: Path, mtime: float) -> None:
        self.indexing = path.name
        document = read_document(path)
        passages = split(document.text)
        vectors = []
        for start in range(0, len(passages), EMBED_BATCH):
            batch = passages[start : start + EMBED_BATCH]
            vectors.extend(self.embedder.documents([p.text for p in batch]))
        self.store.add(path, mtime, document.pages, passages, vectors)
        log.info("Bibliothèque : %s indexé (%d passages)", path.name, len(passages))

    # --- ajout / retrait (écran de réglages) -------------------------------------------------

    def add_files(self, paths: list[Path]) -> list[Path]:
        """Copie les fichiers dans la bibliothèque (les originaux ne bougent pas)."""
        copied = []
        for path in paths:
            if path.suffix.lower() not in SUPPORTED:
                continue
            target = self.folder / path.name
            if path.resolve() != target.resolve():
                shutil.copy2(path, target)
            copied.append(target)
        return copied

    def retire(self, path: str) -> Path | None:
        """Retire un document : déplacé dans _retires (récupérable), puis oublié de l'index."""
        source = Path(path)
        target = None
        if source.is_file():
            retired = self.folder / RETIRED
            retired.mkdir(exist_ok=True)
            target = retired / source.name
            shutil.move(str(source), str(target))
        self.store.remove(path)
        return target

    # --- recherche ---------------------------------------------------------------------------

    def knows(self, question: str) -> list[str]:
        """Documents qui parlent clairement de ce sujet ([] sinon). Mesuré sur un vrai guide :
        sujets liés 0,43–0,63, sans rapport ≤ 0,16. Gardé pour la question en cours."""
        if self._known[0] == question:
            return self._known[1]
        names: list[str] = []
        if question.strip() and self.store.documents():
            try:
                found = self.store.by_meaning(self.embedder.query(question), CANDIDATES)
                close = [i for i, score in found if score >= MIN_SIMILARITY]
                names = list(dict.fromkeys(h.document for h in self.store.hits(close)))[:3]
            except Exception as error:  # modèle d'embeddings indisponible : tant pis
                log.warning("Bibliothèque : sujet non vérifié (%s)", error)
        self._known = (question, names)
        return names

    def auto_search(self, question: str) -> tuple[str, dict] | None:
        """Avant de répondre : la bibliothèque connaît le sujet → on y cherche d'office (un
        petit modèle qui « croit savoir » n'y pense pas tout seul, constaté). Jamais pour une
        question sur le présent."""
        if about_now(question) or not self.knows(question):
            return None
        return ("search_library", {"query": question})

    def hint(self, question: str) -> str:
        """Consigne qui accompagne les passages cherchés d'office ("" si rien)."""
        names = self.knows(question)
        if not names or about_now(question):
            return ""
        return (
            f"Des passages de la bibliothèque ({', '.join(names)}) viennent d'être cherchés "
            "pour cette question : réponds à partir d'eux et cite le document. Leurs chiffres "
            "sont des exemples : jamais un cours ou un prix actuel (pour ça : web_search). "
            "Internet seulement en complément, ou pour l'actualité."
        )

    def search(self, query: str, limit: int = 4) -> list[Hit]:
        by_meaning = self.store.by_meaning(self.embedder.query(query), CANDIDATES)
        best = by_meaning[0][1] if by_meaning else 0.0
        if best >= MIN_SIMILARITY:
            # Seulement les passages presque aussi proches que le meilleur : sinon des
            # passages hors sujet comblent la liste (« pip » → un passage sur le pain).
            by_meaning = [(i, score) for i, score in by_meaning if score >= best - CLOSE_TO_BEST]
            by_words = self.store.by_words(query, CANDIDATES)
        else:
            # Le sens ne suffit pas : seuls les passages avec TOUS les mots importants
            # comptent (un sigle comme « BCE », « EUR/USD ») ; sinon, rien de pertinent.
            by_words = self.store.by_words(query, CANDIDATES, every_word=True)
            if not by_words:
                return []
            by_meaning = []
        scores: dict[int, float] = {}
        for ranking in ([i for i, _ in by_meaning], by_words):
            for rank, passage_id in enumerate(ranking):
                scores[passage_id] = scores.get(passage_id, 0.0) + 1 / (RRF_K + rank + 1)
        top = sorted(scores, key=lambda i: -scores[i])[:limit]
        return self.store.hits(top)
