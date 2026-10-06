"""Vérifie au démarrage que le modèle tient entièrement dans la mémoire vidéo.

Une mémoire de travail trop grande (OLLAMA_NUM_CTX) fait déborder une partie du modèle sur
le processeur : Friday devient plusieurs fois plus lente, sans autre signe. On le dit.
"""

import logging

log = logging.getLogger(__name__)

ADVICE = (
    "réduisez la mémoire de travail (Réglages → Général) ou compressez-la : variables "
    "Windows OLLAMA_FLASH_ATTENTION=1 et OLLAMA_KV_CACHE_TYPE=q8_0, puis redémarrez Ollama."
)


def gpu_share(client, model: str) -> float | None:
    """Part du modèle chargé en mémoire vidéo (1.0 = tout), None si inconnue."""
    try:
        for loaded in client.ps().models:
            if loaded.model == model or loaded.name == model:
                return loaded.size_vram / loaded.size if loaded.size else None
    except Exception as error:  # vérification facultative
        log.debug("Vérification de la mémoire vidéo impossible : %s", error)
    return None


def warn_if_spilling(client, model: str, num_ctx: int) -> str | None:
    """Message d'avertissement si le modèle déborde sur le processeur, sinon None."""
    share = gpu_share(client, model)
    if share is None or share >= 0.99:
        return None
    message = (
        f"{model} ne tient pas dans la carte graphique ({share:.0%} dessus, mémoire de travail "
        f"{num_ctx} jetons) : Friday sera lente. Pour corriger, {ADVICE}"
    )
    log.warning(message)
    return message
