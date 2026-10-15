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

# Mode globe : le gros modèle remplacé par un petit, pour TOUS les appels (réponse, mémoire,
# tri des mails, rêve…) : aucun ne recharge le gros à côté du globe. {gros: petit}
STAND_IN: dict[str, str] = {}
NO_THINK: set[str] = set()  # remplaçants sans réflexion : Ollama refuserait think=True


def _stand_in(kwargs: dict) -> dict:
    small = STAND_IN.get(kwargs.get("model", ""))
    if small:
        kwargs["model"] = small
        if small in NO_THINK:
            kwargs.pop("think", None)
    return kwargs


class GatedClient(ollama.Client):
    """Client Ollama de Friday : chaque appel qui chargerait un modèle passe par la barrière."""

    def chat(self, *args, **kwargs):
        OPEN.wait()
        return super().chat(*args, **_stand_in(kwargs))

    def generate(self, *args, **kwargs):
        OPEN.wait()
        return super().generate(*args, **_stand_in(kwargs))

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
