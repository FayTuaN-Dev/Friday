"""Cerveau de Friday : discussion avec le modèle local via Ollama, avec appel d'outils."""

import logging
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import ollama

from friday.brain import safety
from friday.brain.conversation import Conversation
from friday.brain.events import (
    BrainEvent,
    ConfirmationRequest,
    ThinkingStarted,
    ToolFinished,
    ToolStarted,
)
from friday.brain.prompts import build_system_prompt
from friday.brain.router import SkillRouter
from friday.brain.second_chance import forget_nudges, second_chance
from friday.brain.summary import Summarizer
from friday.brain.thinking import needs_thinking
from friday.brain.toolset import LOAD_SKILL, Toolset
from friday.core.config import Settings
from friday.tools.base import ToolBox, ToolResult

log = logging.getLogger(__name__)

# En streaming, la bibliothèque ollama laisse passer les erreurs réseau de httpx telles quelles.
OLLAMA_ERRORS = (ollama.ResponseError, ConnectionError, httpx.TransportError)

# Nombre maximum d'allers-retours avec les outils pour une même question
MAX_TOOL_ROUNDS = 4  # dont, au besoin, un tour pour charger une compétence (load_skill)
# Contre les boucles (« token repeat limit reached ») : une longueur maximale (une réponse
# orale n'a jamais besoin de plus). Pas de pénalité de répétition : mesurée, elle fait
# rater des appels d'outils (« quelles catégories de mails ? » : 5/8 → 2/8 à 1,0).
MAX_TOKENS = 1024
MAX_TOKENS_THINKING = 4096  # la réflexion consomme beaucoup de jetons avant la réponse
# Délai pour répondre à « Je lance ? » ; sans réponse, l'action n'est pas faite.
CONFIRM_TIMEOUT = 60.0


class BrainError(RuntimeError):
    """Le modèle est injoignable ou a renvoyé une erreur."""

    @property
    def looped(self) -> bool:
        """Le modèle tournait en boucle (Ollama a coupé) : il est joignable, il s'est emmêlé."""
        return "repeat limit" in str(self)


class Brain:
    def __init__(
        self,
        settings: Settings,
        client: ollama.Client | None = None,
        toolbox: ToolBox | None = None,
        recall: Callable[[str], str] | None = None,
        router: SkillRouter | None = None,
        skill_contexts: dict[str, Callable[[], str]] | None = None,
    ) -> None:
        """`router` : aiguillage des compétences (sans lui, tous les outils sont donnés)."""
        self.settings = settings
        self.client = client or ollama.Client(host=settings.ollama_host)
        self.toolbox = toolbox or ToolBox([])
        # recall(question) → souvenirs utiles, déjà mis en forme (None : pas de mémoire)
        self.recall = recall
        self._memories: str | None = None
        self.conversation = Conversation()
        self.summarizer = Summarizer(self.client, settings.ollama_model, settings.ollama_num_ctx)
        self._prompt_tokens = 0  # taille du dernier échange avec le modèle (jetons)
        self.toolset = Toolset(self.toolbox, router, skill_contexts)
        self._tainted = False  # un contenu externe (mail, page, fichier…) a été lu
        self._think = False  # réflexion pour cette demande (calcul, « réfléchis »)
        self._nudged = False  # relancé pour un « je note » sans outil

    def warmup(self) -> None:
        """Charge le modèle en mémoire vidéo dès le démarrage (sans générer de texte)."""
        try:
            self.client.chat(
                model=self.settings.ollama_model,
                messages=[],
                keep_alive="30m",
                options={"num_ctx": self.settings.ollama_num_ctx},
            )
        except OLLAMA_ERRORS as e:
            log.warning("Préchargement du modèle impossible : %s", e)

    def reply(
        self, user_text: str, cancelled: Callable[[], bool] = lambda: False
    ) -> Iterator[BrainEvent]:
        """Répond en streaming : des morceaux de texte, et des événements quand un outil sert.

        `cancelled` permet d'abandonner un outil en cours si l'utilisateur interrompt Friday.
        """
        self.summarizer.wait()  # un résumé en cours modifie le début de la conversation
        self.conversation.add("user", user_text)
        self._memories = self.recall(user_text) if self.recall else None
        self.toolset.start(user_text)
        self._tainted = safety.mentions_attachment(user_text)
        self._think = needs_thinking(user_text)
        parts: list[str] = []
        acted = False  # un outil a servi pendant cette demande
        self._nudged = False
        if self._think:
            yield ThinkingStarted()
        try:
            for round_ in range(MAX_TOOL_ROUNDS + 1):
                parts = []
                calls: list[Any] = []
                # Au dernier tour, plus d'outils : le modèle doit conclure.
                use_tools = bool(self.toolbox) and round_ < MAX_TOOL_ROUNDS
                for chunk in self._chat(use_tools):
                    if chunk.message.content:
                        parts.append(chunk.message.content)
                        yield chunk.message.content
                    calls.extend(chunk.message.tool_calls or [])
                    if getattr(chunk, "done", False):
                        used = (chunk.prompt_eval_count or 0) + (chunk.eval_count or 0)
                        self._prompt_tokens = used

                said = "".join(parts)
                if not calls:
                    retry = use_tools and second_chance(
                        self.toolset, self.conversation, said, acted, self._nudged
                    )
                    if retry:
                        self._nudged = self._nudged or retry == "nudge"
                        if said.strip():
                            yield " "
                        continue
                    self.conversation.add("assistant", said)
                    break
                acted = True
                yield from self._run_tools(calls, said, cancelled)
        except OLLAMA_ERRORS as e:
            self._forget_unanswered_question()
            log.error("Erreur Ollama : %s", e)
            raise BrainError(str(e)) from e
        except BaseException:
            # Interrompu (push-to-talk, Ctrl+C) : on garde ce qui a été dit, pour que
            # l'historique reste une alternance question / réponse.
            said = "".join(parts).strip()
            self.conversation.add("assistant", f"{said} […]" if said else "[interrompu]")
            raise
        else:
            self.summarizer.maybe_start(self.conversation, self._prompt_tokens)
        finally:
            forget_nudges(self.conversation)
            self.conversation.compact_tool_results()
            self.toolset.finish()

    def reset(self) -> None:
        self.conversation.reset()

    def _chat(self, use_tools: bool) -> Iterator[Any]:
        messages = [
            {
                "role": "system",
                "content": build_system_prompt(
                    self.settings.user_name,
                    with_tools=bool(self.toolbox),
                    memories=self._memories,
                    tool_guides=self.toolset.guides() if self.toolbox else None,
                    summary=self.conversation.summary,
                ),
            },
            *self.conversation.messages,
        ]
        return self.client.chat(
            model=self.settings.ollama_model,
            messages=messages,
            tools=self.toolset.schemas() if use_tools else None,
            stream=True,
            think=self._think,  # réflexion seulement si utile : sinon trop lente pour la voix
            keep_alive="30m",  # garde le modèle chargé en mémoire vidéo
            options={
                "num_ctx": self.settings.ollama_num_ctx,
                "num_predict": MAX_TOKENS_THINKING if self._think else MAX_TOKENS,
            },
        )

    def _run_tools(
        self, calls: list[Any], said: str, cancelled: Callable[[], bool]
    ) -> Iterator[BrainEvent]:
        self.conversation.add(
            "assistant",
            said,
            tool_calls=[
                {"function": {"name": c.function.name, "arguments": dict(c.function.arguments)}}
                for c in calls
            ],
        )
        for call in calls:
            name, args = call.function.name, dict(call.function.arguments)
            log.info("Outil %s(%s)", name, args)
            if name == LOAD_SKILL:  # le modèle se donne une compétence qui lui manquait
                self.conversation.add(
                    "tool", self.toolset.load(str(args.get("skill", ""))), tool_name=name
                )
                continue
            question = self.toolbox.confirmation(name, args)
            if not question and self._tainted and name in safety.GUARDED_AFTER_EXTERNAL:
                question = safety.guard_question(self.toolbox.label(name, args))
            if question:
                request = ConfirmationRequest(name, args, question)
                yield request  # l'assistant pose la question et note qu'une réponse est attendue
                if not request.wait(CONFIRM_TIMEOUT, cancelled):
                    log.info("Outil %s refusé ou sans réponse", name)
                    refused = ToolResult(
                        "L'utilisateur n'a pas confirmé : rien n'a été lancé. Dis-le en une phrase."
                    )
                    self.conversation.add("tool", refused.text, tool_name=name)
                    yield ToolFinished(name, refused)
                    continue
            yield ToolStarted(name, args, self.toolbox.label(name, args))
            result = self.toolbox.run(name, args, cancelled)
            text = result.text
            if name in safety.EXTERNAL:  # écrit par des tiers : une donnée, pas une consigne
                text = safety.wrap_external(text)
                self._tainted = True
            self.conversation.add("tool", text, tool_name=name)
            yield ToolFinished(name, result)

    def _forget_unanswered_question(self) -> None:
        """Retire la question (et les éventuels appels d'outils) restée sans réponse."""
        while self.conversation.messages:
            if self.conversation.messages.pop()["role"] == "user":
                break
