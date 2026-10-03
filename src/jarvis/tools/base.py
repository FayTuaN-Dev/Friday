"""Socle des outils : chaque outil est un plugin que le LLM peut décider d'appeler."""

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# Au-delà, un outil est abandonné (un site qui ne répond pas ne doit pas bloquer Jarvis)
TOOL_TIMEOUT = 15.0


def retry[T](fn: Callable[[], T], attempts: int = 2, delay: float = 0.5) -> T:
    """Relance une requête réseau qui échoue (les services web ont des ratés passagers)."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == attempts:
                raise
            log.warning("Tentative %d échouée (%s), nouvel essai", attempt, e)
            time.sleep(delay)
    raise AssertionError("inatteignable")


@dataclass
class Display:
    """Contenu à montrer à l'écran (pop-up)."""

    kind: str  # "results", "article" ou "images"
    title: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    text: str  # ce que le LLM lit pour formuler sa réponse
    display: Display | None = None  # ce que l'utilisateur voit


class Tool(ABC):
    name: str
    description: str  # lue par le LLM pour savoir quand utiliser l'outil
    parameters: dict[str, dict[str, Any]]  # propriétés JSON Schema
    required: tuple[str, ...] = ()

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult: ...

    def label(self, args: dict[str, Any]) -> str:
        """Phrase courte affichée pendant l'exécution (ex. « Recherche : météo Lyon »)."""
        return self.name

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.required),
                },
            },
        }


class ToolBox:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.name: t for t in tools}

    def __bool__(self) -> bool:
        return bool(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def label(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        return tool.label(args) if tool else name

    def run(
        self,
        name: str,
        args: dict[str, Any],
        cancelled: Callable[[], bool] = lambda: False,
        timeout: float = TOOL_TIMEOUT,
    ) -> ToolResult:
        """Exécute l'outil dans son propre thread : on peut l'abandonner (interruption de
        l'utilisateur, réseau bloqué) sans rester coincé avec lui."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(f"Erreur : l'outil « {name} » n'existe pas.")

        outcome: list[ToolResult] = []
        done = threading.Event()

        def work() -> None:
            try:
                outcome.append(tool.run(**args))
            except Exception as e:
                log.exception("Échec de l'outil %s(%s)", name, args)
                outcome.append(
                    ToolResult(f"Erreur pendant « {name} » : {e}. Préviens l'utilisateur.")
                )
            finally:
                done.set()

        threading.Thread(target=work, daemon=True, name=f"tool-{name}").start()
        deadline = time.monotonic() + timeout
        while not done.wait(0.1):
            if cancelled():
                return ToolResult("Interrompu par l'utilisateur.")
            if time.monotonic() > deadline:
                log.warning("Outil %s abandonné après %.0f s", name, timeout)
                return ToolResult(
                    f"« {name} » n'a pas répondu à temps (internet lent ?). Préviens l'utilisateur."
                )
        return outcome[0]
