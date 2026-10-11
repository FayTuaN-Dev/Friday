"""Choisir quoi lancer pour « Nova », « l'album Discovery », « du Daft Punk » : les playlists
de l'utilisateur d'abord, puis la recherche Spotify ; le nom le plus proche gagne, aidé par
le type demandé (« playlist », « album », « artiste », « chanson »)."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from friday.voice.wake import normalize

HINTS = (("playlist", "playlist"), ("album", "album"), ("artiste", "artist"),
         ("groupe", "artist"), ("chanteur", "artist"), ("chanteuse", "artist"),
         ("chanson", "track"), ("titre", "track"), ("morceau", "track"))  # fmt: skip
# Mots qui entourent ce qu'on cherche (« mets-moi un peu de … sur Spotify »)
FILLER = (
    r"\b(?:mets?(?: moi)?|lance|joue|ecoute|ecouter|passe|sur spotify|spotify|musique|"
    r"s il te plait|stp|un peu|ma|mon|mes|la|le|les|l|du|de la|des|d|de|une?|son)\b"
)


@dataclass(frozen=True)
class Choice:
    kind: str  # playlist, album, artist, track
    name: str
    uri: str
    by: str = ""  # artiste (album, titre) ou propriétaire (playlist)
    mine: bool = False  # une playlist de l'utilisateur


def clean(query: str) -> tuple[str, str]:
    """(ce qu'on cherche, type demandé ou "") : « ma playlist Nova » → (« nova », playlist)."""
    words = normalize(query)
    hint = next((kind for word, kind in HINTS if re.search(rf"\b{word}s?\b", words)), "")
    for word, _ in HINTS:
        words = re.sub(rf"\b{word}s?\b", " ", words)
    words = re.sub(FILLER, " ", words)
    return " ".join(words.split()) or normalize(query), hint


def similarity(wanted: str, choice: Choice) -> float:
    name = normalize(choice.name)
    if name == wanted:
        return 1.0
    full = f"{name} {normalize(choice.by)}".strip()
    best = max(
        SequenceMatcher(None, wanted, name).ratio(), SequenceMatcher(None, wanted, full).ratio()
    )
    if wanted and (f" {wanted} " in f" {name} "):  # « nova » dans « radio nova »
        best = max(best, 0.75)
    return best


def best(query: str, choices: list[Choice]) -> Choice | None:
    wanted, hint = clean(query)
    if not choices:
        return None

    def score(choice: Choice) -> float:
        bonus = 0.25 * choice.mine + (0.4 if hint and choice.kind == hint else 0)
        return similarity(wanted, choice) + bonus

    return max(choices, key=score)  # à égalité : l'ordre (ses playlists, puis Spotify)


def describe(choice: Choice) -> str:
    """Pour le dire : « ta playlist « Nova » », « l'album « Discovery » de Daft Punk »…"""
    by = f" de {choice.by}" if choice.by else ""
    if choice.kind == "playlist":
        return f"ta playlist « {choice.name} »" if choice.mine else f"la playlist « {choice.name} »"
    if choice.kind == "album":
        return f"l'album « {choice.name} »{by}"
    if choice.kind == "artist":
        return f"les titres de {choice.name}"
    return f"« {choice.name} »{by}"
