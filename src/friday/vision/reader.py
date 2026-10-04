"""Lecture d'une capture d'écran par un petit modèle de vision local (Ollama).

Le modèle de vision lit très bien (textes, code, erreurs) mais calcule mal sans réfléchir :
il DÉCRIT et RECOPIE ce qui sert à la question, et c'est le cerveau habituel (qwen3) qui
répond à partir de ce texte. Les deux modèles ne tiennent pas ensemble dans 8 Go de mémoire
vidéo : la vision est déchargée aussitôt (keep_alive=0) pour que qwen3 revienne vite.
"""

import logging

import ollama

log = logging.getLogger(__name__)

INSTRUCTIONS = """Tu regardes une capture de l'écran de l'utilisateur. Sa question : « {question} »

Décris en français ce qui est utile pour y répondre :
- dis brièvement quelle application ou quelle page est affichée ;
- recopie MOT POUR MOT les textes importants : messages d'erreur, codes, titres, nombres,
  extraits de code, contenu d'un tableau ;
- ne fais aucun calcul et ne réponds pas toi-même à la question : décris seulement.
Sois factuel, sans Markdown, 15 lignes au maximum."""


class VisionUnavailable(Exception):
    pass


class ScreenReader:
    def __init__(self, client: ollama.Client, model: str) -> None:
        self.client = client
        self.model = model

    def describe(self, image: bytes, question: str) -> str:
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": INSTRUCTIONS.format(question=question or "que vois-tu ?"),
                        "images": [image],
                    }
                ],  # fmt: skip
                think=False,
                keep_alive=0,  # libère la mémoire vidéo pour qwen3
                options={"num_ctx": 4096, "temperature": 0.2},
            )
        except ollama.ResponseError as error:
            if error.status_code == 404:
                raise VisionUnavailable(
                    f"Le modèle de vision « {self.model} » n'est pas installé "
                    f"(commande : ollama pull {self.model})."
                ) from error
            raise
        text = (response.message.content or "").strip()
        log.info("Écran décrit en %d caractères", len(text))
        return text
