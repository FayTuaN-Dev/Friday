"""Préparation du texte pour la synthèse vocale."""

import re

# Fin de phrase : ponctuation forte suivie d'un espace ou d'un retour à la ligne.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")
# Coupure de secours pour les phrases trop longues sans point.
_SOFT_BREAK = re.compile(r"[,;:]\s")

_URL = re.compile(r"https?://\S+")
_MARKDOWN = re.compile(r"[*_#`>|~]+")
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️]")
_SPACES = re.compile(r"\s+")


def clean_for_speech(text: str) -> str:
    """Retire ce qui ne se prononce pas : Markdown, émojis, liens."""
    text = _URL.sub("ce lien", text)
    text = _MARKDOWN.sub("", text)
    text = _EMOJI.sub("", text)
    return _SPACES.sub(" ", text).strip()


def apply_pronunciations(text: str, pronunciations: dict[str, str]) -> str:
    """Remplace certains mots par une graphie que la voix prononce mieux
    (« Friday » → « Fraille dé », pour une prononciation à l'anglaise)."""
    for word, spoken in pronunciations.items():
        text = re.sub(rf"\b{re.escape(word)}\b", spoken, text, flags=re.IGNORECASE)
    return text


class SentenceSplitter:
    """Reçoit le texte morceau par morceau et rend les phrases dès qu'elles sont complètes."""

    def __init__(self, max_chars: int = 200) -> None:
        self.max_chars = max_chars
        self._buffer = ""

    def feed(self, chunk: str) -> list[str]:
        self._buffer += chunk
        parts = _SENTENCE_END.split(self._buffer)
        self._buffer = parts.pop()  # le dernier morceau n'est pas (encore) une phrase complète
        sentences = [p.strip() for p in parts if p.strip()]

        # Phrase trop longue : on coupe à la dernière virgule avant la limite, tant qu'il y en a.
        while len(self._buffer) > self.max_chars:
            breaks = list(_SOFT_BREAK.finditer(self._buffer, 0, self.max_chars))
            if not breaks:
                break
            cut = breaks[-1].end()
            sentences.append(self._buffer[:cut].strip())
            self._buffer = self._buffer[cut:]
        return sentences

    def flush(self) -> list[str]:
        rest, self._buffer = self._buffer.strip(), ""
        return [rest] if rest else []
