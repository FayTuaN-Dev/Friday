"""Repérer le mot d'activation (« Friday ») au début d'une phrase transcrite."""

import re
import unicodedata

# Mots d'interruption : « Friday, stop » coupe la parole sans nouvelle question.
STOP_COMMANDS = {
    "stop", "arrete", "arrete toi", "tais toi", "silence", "chut",
    "c est bon", "ca suffit", "ca ira", "merci c est bon",
}  # fmt: skip
# Petits mots qui peuvent précéder le nom (« Hé Friday », « OK Friday »)
PREFIXES = r"(?:h[ée]|hey|eh|et|ok|okay|dis|bon)?"


def normalize(text: str) -> str:
    """minuscules, sans accents ni ponctuation : « Arrête-toi ! » → « arrete toi »."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def wake_pattern(wake_words: list[str]) -> re.Pattern[str]:
    names = "|".join(re.escape(w) for w in sorted(wake_words, key=len, reverse=True))
    # Le nom doit être au début (éventuellement après « hé », « ok »…).
    return re.compile(rf"^\W*{PREFIXES}\W*(?:{names})\b[\s,.!?;:…-]*", re.IGNORECASE)


def split_wake_word(text: str, pattern: re.Pattern[str]) -> str | None:
    """Renvoie la demande qui suit le nom, "" si le nom est seul, None s'il est absent."""
    match = pattern.match(text.strip())
    if not match:
        return None
    command = text.strip()[match.end() :].strip()
    return command[:1].upper() + command[1:]


def is_stop(command: str) -> bool:
    return normalize(command) in STOP_COMMANDS


def is_stop_request(text: str, max_words: int = 4) -> bool:
    """Phrase courte qui se termine par un ordre d'arrêt (« Ravi, stop » = « Friday, stop » mal
    compris)."""
    words = normalize(text).split()
    if not words or len(words) > max_words:
        return False
    return any(" ".join(words[i:]) in STOP_COMMANDS for i in range(len(words)))


def similarity(a: str, b: str) -> float:
    """Part des mots de `a` présents dans `b` (pour reconnaître l'écho de la voix de Friday)."""
    words_a, words_b = set(normalize(a).split()), set(normalize(b).split())
    if not words_a:
        return 0.0
    return len(words_a & words_b) / len(words_a)
