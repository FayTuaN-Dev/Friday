"""Seconde chance : la réponse finale du modèle est suspecte, on le relance une fois.

1. Réponse vide : il a sans doute appelé un outil qui ne lui était pas proposé (Ollama
   l'efface sans rien dire) : on réessaie avec toutes les compétences.
2. « Je note » sans avoir rien noté (qwen3, sur des demandes vagues comme « pour le moment
   on sauvegarde juste les points d'intérêt ») : on le relance pour qu'il le fasse vraiment.
"""

import logging

from friday.brain.conversation import Conversation
from friday.brain.toolset import Toolset
from friday.voice.wake import normalize

log = logging.getLogger(__name__)

NOTE_TOOL = "add_note"
CLAIMS = (" je note", " c est note", " j ai note", " je sauvegarde", " sauvegarde ",
          " sauvegardes", " enregistre ", " enregistres", " de cote")  # fmt: skip

NUDGE = (
    "Vérification automatique : tu viens de dire que tu notais ou sauvegardais, mais aucun "
    "outil n'a été appelé : rien n'est enregistré. Appelle add_note maintenant (une note par "
    "point, dans une liste au nom du sujet). Ensuite, confirme en quelques mots seulement "
    "(ex. « C'est enregistré dans la liste Forex. ») : ta phrase précédente a déjà été dite."
)


def claims_saved(text: str) -> bool:
    padded = f" {normalize(text)} "
    return any(claim in padded for claim in CLAIMS)


def second_chance(
    toolset: Toolset, conversation: Conversation, said: str, acted: bool, nudged: bool
) -> str | None:
    """« widen », « nudge » (relance déjà ajoutée à la conversation) ou None."""
    if not said.strip() and toolset.widen():
        log.warning("Réponse vide : nouvel essai avec toutes les compétences")
        return "widen"
    if not acted and not nudged and claims_saved(said) and NOTE_TOOL in toolset.tool_names():
        log.warning("« Je note » sans outil : relance pour enregistrer vraiment")
        conversation.add("assistant", said)
        conversation.messages.append({"role": "system", "content": NUDGE})
        return "nudge"
    return None


def forget_nudges(conversation: Conversation) -> None:
    """La relance ne reste pas dans l'historique."""
    conversation.messages[:] = [m for m in conversation.messages if m["content"] is not NUDGE]
