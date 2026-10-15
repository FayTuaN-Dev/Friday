"""Recharger les modèles de Friday dans le bon ordre (mode jeu, mode globe)."""

import logging
from typing import TYPE_CHECKING

from friday.brain import gpu_gate

if TYPE_CHECKING:
    from friday.app.assistant import Assistant

log = logging.getLogger(__name__)


def reload_in_startup_order(a: "Assistant") -> None:
    """Le même ordre qu'au démarrage : modèle de la mémoire, qwen, PUIS Whisper. Mesuré :
    Whisper rechargé d'abord, qwen débordait de la carte et lisait 200 jetons/s au lieu
    de 1 550 (carte à 97 %, Friday semblait figée)."""
    settings = a.settings
    if getattr(settings, "memory_enabled", False):
        try:
            a.components.brain.client.embed(model=settings.embed_model, input=["réveil"],
                                            keep_alive="30m")  # fmt: skip
        except Exception as error:
            log.warning("Modèle de la mémoire non rechargé (%s)", error)
    a.components.brain.warmup()
    if a.components.stt is not None:
        a.components.stt.reload()


def swap_brain(a: "Assistant", small: str | None, thinks: bool = True) -> None:
    """Change le modèle de conversation : `small` remplace le gros (mode globe), None le
    rend. Tout est déchargé puis rechargé dans l'ordre du démarrage ; pendant ce temps, la
    barrière retient les autres appels (aucun ne recharge le mauvais modèle)."""
    gpu_gate.OPEN.clear()
    try:
        gpu_gate.unload_all(a.components.brain.client)
        if a.components.stt is not None:
            a.components.stt.unload()
        gpu_gate.STAND_IN.clear()
        gpu_gate.NO_THINK.clear()
        if small:
            gpu_gate.STAND_IN[a.settings.ollama_model] = small
            if not thinks:
                gpu_gate.NO_THINK.add(small)
        gpu_gate.OPEN.set()
        reload_in_startup_order(a)
    finally:
        gpu_gate.OPEN.set()
