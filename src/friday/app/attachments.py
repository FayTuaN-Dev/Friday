"""Ce qui accompagne une demande, ajouté par Friday elle-même (pas par le LLM) :
- les fichiers glissés dans la fenêtre, joints à la prochaine demande (écrite ou dite) ;
- le contenu du presse-papier, quand la demande en parle (« ce que j'ai copié »).

Le modèle local oublie souvent d'appeler l'outil du presse-papier (« je vais le lire… » sans
le faire) : on lui donne directement le contenu, c'est fiable.
"""

import logging
import re
import threading
from collections.abc import Callable
from pathlib import Path

from friday.files.clipboard import ClipboardContent, ClipboardError

log = logging.getLogger(__name__)

CLIPBOARD_WORDS = re.compile(r"\b(copi[ée]e?s?|presse[- ]?papiers?|clipboard)\b", re.IGNORECASE)
CLIPBOARD_MAX_CHARS = 6000


class Attachments:
    def __init__(self, clipboard: Callable[[], ClipboardContent] | None = None) -> None:
        self._pending: list[Path] = []
        self._lock = threading.Lock()
        self._clipboard = clipboard  # None : pas d'accès au presse-papier

    def add(self, path: Path) -> None:
        with self._lock:
            if path not in self._pending:
                self._pending.append(path)

    def wrap(self, request: str) -> str:
        """La demande, précédée de ce qui l'accompagne (fichiers joints une seule fois)."""
        with self._lock:
            files, self._pending = self._pending, []
        lines = [f"[Fichier joint : {path}]" for path in files]
        if self._clipboard and CLIPBOARD_WORDS.search(request):
            lines += self._clipboard_lines()
        return "\n".join([*lines, request]) if lines else request

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
