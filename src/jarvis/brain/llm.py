"""Cerveau de Jarvis : discussion avec le modèle local via Ollama."""

import logging
from collections.abc import Iterator

import ollama

from jarvis.brain.conversation import Conversation
from jarvis.brain.prompts import build_system_prompt
from jarvis.core.config import Settings

log = logging.getLogger(__name__)


class BrainError(RuntimeError):
    """Le modèle est injoignable ou a renvoyé une erreur."""


class Brain:
    def __init__(self, settings: Settings, client: ollama.Client | None = None) -> None:
        self.settings = settings
        self.client = client or ollama.Client(host=settings.ollama_host)
        self.conversation = Conversation()

    def warmup(self) -> None:
        """Charge le modèle en mémoire vidéo dès le démarrage (sans générer de texte)."""
        try:
            self.client.chat(
                model=self.settings.ollama_model,
                messages=[],
                keep_alive="30m",
                options={"num_ctx": self.settings.ollama_num_ctx},
            )
        except (ollama.ResponseError, ConnectionError) as e:
            log.warning("Préchargement du modèle impossible : %s", e)

    def reply(self, user_text: str) -> Iterator[str]:
        """Envoie le message et renvoie la réponse morceau par morceau (streaming)."""
        self.conversation.add("user", user_text)
        messages = [
            {"role": "system", "content": build_system_prompt(self.settings.user_name)},
            *self.conversation.messages,
        ]

        parts: list[str] = []
        try:
            stream = self.client.chat(
                model=self.settings.ollama_model,
                messages=messages,
                stream=True,
                think=False,  # le mode « réflexion » de qwen3 est trop lent pour la voix
                keep_alive="30m",  # garde le modèle chargé en mémoire vidéo
                options={"num_ctx": self.settings.ollama_num_ctx},
            )
            for chunk in stream:
                text = chunk.message.content
                if text:
                    parts.append(text)
                    yield text
        except (ollama.ResponseError, ConnectionError) as e:
            self.conversation.messages.pop()  # on oublie la question restée sans réponse
            log.error("Erreur Ollama : %s", e)
            raise BrainError(str(e)) from e

        self.conversation.add("assistant", "".join(parts))

    def reset(self) -> None:
        self.conversation.reset()
