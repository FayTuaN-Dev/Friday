"""Mode jeu (G1) : la carte graphique est rendue au jeu. Tant qu'elle est fermée, tout appel
à Ollama (réponse, tri des mails, mémoire, rêve…) ATTEND la réouverture au lieu de recharger
un modèle en pleine partie. Le déchargement, lui, passe toujours."""

import logging
import threading

import ollama

from friday.brain.vram import wait_unloaded

log = logging.getLogger(__name__)

OPEN = threading.Event()
OPEN.set()  # ouverte : Friday travaille normalement


class GatedClient(ollama.Client):
    """Client Ollama de Friday : chaque appel qui chargerait un modèle passe par la barrière."""

    def chat(self, *args, **kwargs):
        OPEN.wait()
        return super().chat(*args, **kwargs)

    def generate(self, *args, **kwargs):
        OPEN.wait()
        return super().generate(*args, **kwargs)

    def embed(self, *args, **kwargs):
        OPEN.wait()
        return super().embed(*args, **kwargs)

    def embeddings(self, *args, **kwargs):
        OPEN.wait()
        return super().embeddings(*args, **kwargs)


def unload_all(client: ollama.Client) -> list[str]:
    """Retire de la carte graphique tous les modèles qu'Ollama y a chargés (sans passer par
    la barrière), et attend qu'ils soient vraiment partis. Renvoie leurs noms."""
    try:
        names = [m.model for m in client.ps().models]
    except Exception as error:  # Ollama injoignable : rien à libérer de notre côté
        log.warning("Mode jeu : Ollama ne répond pas (%s)", error)
        return []
    for name in names:
        try:
            ollama.Client.generate(client, model=name, keep_alive=0)
        except Exception as error:
            log.warning("Mode jeu : %s non déchargé (%s)", name, error)
    for name in names:
        wait_unloaded(client, name)
    return names


def unload_mine(client: ollama.Client, mine: tuple[str, ...]) -> list[str]:
    """En quittant Friday : retire SES modèles de la carte graphique, sans attendre (elle
    les gardait 30 min après la dernière réponse). Ceux d'autres logiciels restent."""
    try:
        loaded = [m.model for m in client.ps().models]
    except Exception:  # Ollama injoignable : rien à libérer
        return []
    names = [n for n in loaded if any(n in (m, f"{m}:latest") for m in mine if m)]
    for name in names:
        try:
            ollama.Client.generate(client, model=name, keep_alive=0)
        except Exception as error:
            log.warning("%s non déchargé en quittant (%s)", name, error)
    return names
