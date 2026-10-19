"""Ce qui accompagne une demande, ajouté par Friday elle-même (pas par le LLM) :
- les fichiers glissés dans la fenêtre, joints à la prochaine demande (écrite ou dite) ;
- les fichiers collés dans la demande (« file:///…/capture.png », « C:\\…\\photo.jpg ») ;
- le contenu du presse-papier, quand la demande en parle (« ce que j'ai copié »).

Le modèle local oublie souvent d'appeler l'outil du presse-papier (« je vais le lire… » sans
le faire) : on lui donne directement le contenu, c'est fiable. Une image jointe est décrite
par le modèle de vision local (qwen3 ne lit que du texte) : rien ne part en ligne.
"""

import logging
import re
import threading
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlparse

from friday.files.clipboard import ClipboardContent, ClipboardError

log = logging.getLogger(__name__)

CLIPBOARD_WORDS = re.compile(r"\b(copi[ée]e?s?|presse[- ]?papiers?|clipboard)\b", re.IGNORECASE)
CLIPBOARD_MAX_CHARS = 6000
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
# Un fichier collé dans la demande : une adresse file:/// ou un chemin Windows complet
PASTED = re.compile(r"file:///\S+|\b[A-Za-z]:\\[^\n\"<>|?*]+?\.[A-Za-z0-9]{2,5}\b")

Look = Callable[[Path, str], str]  # (image, question) → description par le modèle de vision


def pasted_files(request: str) -> tuple[str, list[Path]]:
    """Les fichiers existants collés dans la demande, et la demande sans eux."""
    found: list[Path] = []

    def take(match: re.Match) -> str:
        text = match.group(0)
        if text.startswith("file:"):
            text = unquote(urlparse(text).path).lstrip("/")
        path = Path(text)
        if not path.is_file():
            return match.group(0)  # pas un fichier : on laisse le texte tel quel
        found.append(path)
        return ""

    rest = PASTED.sub(take, request)
    return " ".join(rest.split()), found


class Attachments:
    def __init__(self, clipboard: Callable[[], ClipboardContent] | None = None,
                 look: Look | None = None) -> None:  # fmt: skip
        self._pending: list[Path] = []
        self._lock = threading.Lock()
        self._clipboard = clipboard  # None : pas d'accès au presse-papier
        self._look = look  # None : pas de vision, l'image reste un simple fichier joint

    def add(self, path: Path) -> None:
        with self._lock:
            if path not in self._pending:
                self._pending.append(path)

    def wrap(self, request: str) -> str:
        """La demande, précédée de ce qui l'accompagne (fichiers joints une seule fois)."""
        request, pasted = pasted_files(request)
        with self._lock:
            files, self._pending = self._pending, []
        files += [path for path in pasted if path not in files]
        lines = [self._file_line(path, request) for path in files]
        if self._clipboard and CLIPBOARD_WORDS.search(request):
            lines += self._clipboard_lines()
        return "\n".join([*lines, request]) if lines else request

    def _file_line(self, path: Path, request: str) -> str:
        if self._look is None or path.suffix.lower() not in IMAGE_SUFFIXES:
            return f"[Fichier joint : {path}]"
        try:
            description = self._look(path, request)
        except Exception as error:  # modèle de vision absent, image illisible
            log.warning("Image jointe illisible (%s) : %s", path.name, error)
            return f"[Image jointe : {path} — je n'ai pas pu la regarder : {error}]"
        return (f"[Image jointe : {path.name}. Tu la vois grâce à ton modèle de vision, qui "
                "la décrit ci-dessous : réponds à partir de cette description, sans dire que tu "
                f"ne peux pas voir les images.\n{description}\n]")  # fmt: skip

    def _clipboard_lines(self) -> list[str]:
        try:
            content = self._clipboard()
        except ClipboardError as error:
            log.warning("Presse-papier illisible : %s", error)
            return []
        if content.files:  # fichiers copiés dans l'explorateur : lus avec read_file
            return [f"[Fichier copié par l'utilisateur : {path}]" for path in content.files]
        text = content.text.strip()
        if not text:
            return ["[Le presse-papier est vide (ou contient une image).]"]
        if len(text) > CLIPBOARD_MAX_CHARS:
            text = text[:CLIPBOARD_MAX_CHARS] + " [… coupé : trop long]"
        return [f"[Texte copié par l'utilisateur :\n{text}\n]"]
