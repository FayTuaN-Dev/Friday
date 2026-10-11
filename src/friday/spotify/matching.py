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
# Un style de musique (« mets du jazz ») : une playlist, pas l'album « Jazz » de Queen (constaté)
GENRES = {"jazz", "rock", "rap", "pop", "electro", "techno", "house", "lofi", "lo fi", "chill",
          "classique", "reggae", "funk", "soul", "blues", "metal", "country", "disco", "variete",
          "variete francaise", "rnb", "r b", "hip hop", "ambiance", "relax", "detente", "dub",
          "drum and bass", "dance", "afro", "latino", "salsa", "kpop", "musique classique",
          "piano", "acoustique", "annees 80", "annees 90", "annees 2000"}  # fmt: skip
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
    words = " ".join(re.sub(FILLER, " ", words).split()) or normalize(query)
    if not hint and words in GENRES:
        hint = "playlist"
    return words, hint


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


def is_style(query: str) -> bool:
    """« un peu d'électro » : un style, donc une playlist (pas « l'album Electro »)."""
    wanted, hint = clean(query)
    return wanted in GENRES and hint == "playlist"


def best(query: str, choices: list[Choice]) -> Choice | None:
    wanted, hint = clean(query)
    style = is_style(query)
    if style and any(c.kind == "playlist" for c in choices):
        # une playlist seulement (constaté : l'album « Electro » gagnait au nom exact)
        choices = [c for c in choices if c.kind == "playlist"]
    if not choices:
        return None

    def score(choice: Choice) -> float:
        close = similarity(wanted, choice)
        # Ses playlists d'abord… sauf pour un style, où le nom doit vraiment y correspondre
        # (constaté : « Playlist Stream » choisie pour « un peu d'électro »)
        mine = choice.mine and (not style or close >= 0.75)
        return close + 0.25 * mine + (0.4 if hint and choice.kind == hint else 0)

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


# « Mets un peu d'électro » : la musique, lancée par le code. Constaté : qwen répondait « Je
# lance une playlist electro » sans appeler l'outil (il imitait ses réponses précédentes).
VERBS = re.compile(r"^(?:\w+ )?(?:mets?|lance|joue|passe|fais moi ecouter|fait moi ecouter)\b")
NOT_MUSIC = re.compile(r"\b(?:minuteur|rappel|alerte|volume|video|youtube|film|serie|pause|"
                       r"suivante?|precedente?|radio)\b")  # fmt: skip


def music_request(text: str) -> tuple[str, dict] | None:
    """(« play_music », {"query": …}) pour une demande de musique sans ambiguïté : un verbe
    (« mets », « lance », « joue »…) et un style, « playlist », « album », « artiste »,
    « chanson » ou « Spotify ». Le reste (« lance Nova ») : au modèle."""
    said = normalize(text)
    if not VERBS.search(said) or NOT_MUSIC.search(said):
        return None
    wanted, hint = clean(text)
    if not wanted or wanted == said:  # rien de précis (« lance la musique »)
        return None
    if hint or wanted in GENRES or re.search(r"\bspotify\b", said):
        return ("play_music", {"query": text.strip()})
    return None
